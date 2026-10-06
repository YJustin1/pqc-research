/*
 * kem_bench: run KEM operations through either liboqs or OpenSSL, for
 * the timing harness (bench/computational/api/) and the memory harness
 * (bench/memory/).
 *
 *   kem_bench time     <impl> <alg> <op> <max_iters> <max_seconds> <warmup_seconds>
 *   kem_bench prepare  <impl> <alg> <dir>
 *   kem_bench memory   <impl> <alg> <op> <dir>
 *   kem_bench once     <impl> <alg> <op> <dir>
 *   kem_bench baseline <impl> <alg> <op> <dir>
 *   kem_bench version
 *
 *   impl  liboqs | openssl
 *   op    keygen | encaps | decaps
 *
 * time: one process times one operation.
 *   1. Set up the algorithm, generate one keypair, encapsulate to it,
 *      decapsulate, and check that both sides got the same secret.
 *   2. Warm up by running the operation for warmup_seconds.
 *   3. Time the operation until max_iters iterations, or until
 *      max_seconds have passed and at least MIN_ITERS have run.
 *   encaps and decaps reuse the keypair and ciphertext from step 1. Work
 *   that is not the operation itself, such as freeing an OpenSSL key
 *   object, happens outside the timed window.
 *
 * prepare: step 1 above, then write the keypair, ciphertext and shared
 *   secret to files in dir, for memory / once / baseline to load.
 *
 * memory: in-process stack and heap of single calls. Heap is tracked
 *   only in the memory build (-DKEM_MEMORY plus the --wrap linker flags
 *   in MEMORY_WRAP_FLAGS, bench/driver/kem_build.py); elsewhere it is
 *   reported as -1. The timing build therefore carries no tracking, and
 *   gives the stack figures. Loads only the inputs `op` needs, then
 *   measures three calls:
 *     first   the first call in the process, including any one-time
 *             setup the library does on first use;
 *     steady  the larger of the next two calls.
 *   Heap is the peak of live requested bytes during the call, above the
 *   level when it started. Stack is the depth the call wrote to, found
 *   by running it on a separate pattern-filled stack and scanning, minus
 *   the harness's own frames (measured with a no-op, and reported as
 *   stack_overhead_bytes).
 *
 * once / baseline: whole-process measurement under valgrind massif, used
 *   as a cross-check for liboqs. once loads the inputs, runs the
 *   operation once and exits; baseline does the same minus the
 *   operation. Neither uses stdio, and both exit with _exit().
 *
 * memory, once and decaps all check the decapsulated secret against the
 * saved one.
 *
 * Output on stdout, one record per line:
 *   M,<key>,<value>                          metadata
 *   S,<tsc_ticks>,<ns>,<perf_user_cycles>    time only: one per iteration;
 *                                            cycles are -1 without perf
 */
#define _GNU_SOURCE
#include <fcntl.h>
#include <linux/perf_event.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <time.h>
#include <ucontext.h>
#include <unistd.h>
#include <x86intrin.h>

#include <oqs/oqs.h>
#include <openssl/core_names.h>
#include <openssl/crypto.h>
#include <openssl/dh.h>
#include <openssl/err.h>
#include <openssl/evp.h>
#include <openssl/rsa.h>

#define MIN_ITERS 3
#define BUF_MAX 16384 /* comfortably above the largest OpenSSL output here (384 B) */

static void die(const char *msg) {
	fprintf(stderr, "kem_bench: %s\n", msg);
	ERR_print_errors_fp(stderr);
	exit(1);
}

static void print_sizes(size_t public_key, size_t ciphertext, size_t shared_secret) {
	printf("M,public_key_bytes,%zu\n", public_key);
	printf("M,ciphertext_bytes,%zu\n", ciphertext);
	printf("M,shared_secret_bytes,%zu\n", shared_secret);
}

/* ================================================================
 * Files, without stdio (for prepare / once / baseline)
 * ================================================================ */

static void file_path(char *out, size_t cap, const char *dir, const char *name) {
	if ((size_t)snprintf(out, cap, "%s/%s", dir, name) >= cap) die("path too long");
}

static void write_file(const char *dir, const char *name, const void *buf, size_t len) {
	char path[4096];
	file_path(path, sizeof path, dir, name);
	int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0600);
	if (fd < 0) die("cannot create file");
	for (const char *p = buf; len > 0;) {
		ssize_t n = write(fd, p, len);
		if (n <= 0) die("write failed");
		p += n;
		len -= (size_t)n;
	}
	close(fd);
}

/* Read the whole file into buf; die if it does not fit. Returns its length. */
static size_t read_file(const char *dir, const char *name, void *buf, size_t cap) {
	char path[4096];
	file_path(path, sizeof path, dir, name);
	int fd = open(path, O_RDONLY);
	if (fd < 0) die("cannot open input file (run prepare first)");
	size_t len = 0;
	while (len < cap) {
		ssize_t n = read(fd, (char *)buf + len, cap - len);
		if (n < 0) die("read failed");
		if (n == 0) break;
		len += (size_t)n;
	}
	char extra;
	if (len == cap && read(fd, &extra, 1) > 0) die("input file larger than expected");
	close(fd);
	return len;
}

/* ================================================================
 * Counters (for time)
 * ================================================================ */

/* Time-stamp counter: fixed nominal rate on x86_64, full 64 bits. */
static inline uint64_t read_tsc(void) {
	unsigned aux;
	return __rdtscp(&aux);
}

static inline uint64_t now_ns(void) {
	struct timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return (uint64_t)ts.tv_sec * 1000000000u + (uint64_t)ts.tv_nsec;
}

/* Retired core cycles of this process, user space only, so kernel time
 * such as getrandom() is not counted. Returns -1 where the kernel
 * refuses (perf_event_paranoid > 2). */
static int perf_open(void) {
	struct perf_event_attr attr;
	memset(&attr, 0, sizeof attr);
	attr.size = sizeof attr;
	attr.type = PERF_TYPE_HARDWARE;
	attr.config = PERF_COUNT_HW_CPU_CYCLES;
	attr.disabled = 1;
	attr.exclude_kernel = 1;
	attr.exclude_hv = 1;
	return (int)syscall(SYS_perf_event_open, &attr, 0, -1, -1, 0);
}

static void perf_start(int fd) {
	ioctl(fd, PERF_EVENT_IOC_RESET, 0);
	ioctl(fd, PERF_EVENT_IOC_ENABLE, 0);
}

/* Cycles since perf_start (the counter was reset there). */
static int64_t perf_stop(int fd) {
	uint64_t cycles;
	ioctl(fd, PERF_EVENT_IOC_DISABLE, 0);
	if (read(fd, &cycles, sizeof cycles) != sizeof cycles) die("perf read failed");
	return (int64_t)cycles;
}

/* ================================================================
 * Backend interface
 *
 * init()   generates a keypair and a reference ciphertext and checks the
 *          round trip (time, prepare).
 * save()   writes init's keypair, ciphertext and shared secret to dir.
 * load()   reads only what `op` needs from dir (once, baseline).
 * The three operations return 1 on success; cleanup() runs after every
 * operation, outside the timed window. secret() returns the shared
 * secret the last encaps or decaps produced.
 * ================================================================ */

typedef struct {
	void *(*init)(const char *alg);
	void (*save)(void *state, const char *dir);
	void *(*load)(const char *alg, const char *op, const char *dir);
	int (*keygen)(void *state);
	int (*encaps)(void *state);
	int (*decaps)(void *state);
	void (*cleanup)(void *state);
	size_t (*secret)(void *state, const uint8_t **ss);
} backend;

/* ================================================================
 * liboqs
 *
 * Caller-allocated buffers; the harness allocates nothing per call.
 * Saved files hold raw bytes: pk, sk, ct, ss.
 * ================================================================ */

typedef struct {
	OQS_KEM *kem;
	/* reference keypair, ciphertext and shared secret */
	uint8_t *pk, *sk, *ct, *ss;
	/* scratch outputs of the operations */
	uint8_t *out_pk, *out_sk, *out_ct, *out_ss;
} oqs_state;

static oqs_state *oqs_new(const char *alg) {
	OQS_init();
	oqs_state *s = calloc(1, sizeof *s);
	s->kem = OQS_KEM_new(alg);
	if (!s->kem) die("liboqs does not know this algorithm, or it is disabled");
	return s;
}

static void *oqs_init(const char *alg) {
	oqs_state *s = oqs_new(alg);
	size_t pk_len = s->kem->length_public_key;
	size_t sk_len = s->kem->length_secret_key;
	size_t ct_len = s->kem->length_ciphertext;
	size_t ss_len = s->kem->length_shared_secret;
	s->pk = malloc(pk_len);
	s->sk = malloc(sk_len);
	s->ct = malloc(ct_len);
	s->ss = malloc(ss_len);
	s->out_pk = malloc(pk_len);
	s->out_sk = malloc(sk_len);
	s->out_ct = malloc(ct_len);
	s->out_ss = malloc(ss_len);

	if (OQS_KEM_keypair(s->kem, s->pk, s->sk) != OQS_SUCCESS ||
	    OQS_KEM_encaps(s->kem, s->ct, s->ss, s->pk) != OQS_SUCCESS ||
	    OQS_KEM_decaps(s->kem, s->out_ss, s->ct, s->sk) != OQS_SUCCESS)
		die("liboqs setup failed");
	if (memcmp(s->ss, s->out_ss, ss_len) != 0) die("liboqs shared secrets differ");

	print_sizes(pk_len, ct_len, ss_len);
	printf("M,secret_key_bytes,%zu\n", sk_len);
	return s;
}

static void oqs_save(void *state, const char *dir) {
	oqs_state *s = state;
	write_file(dir, "pk", s->pk, s->kem->length_public_key);
	write_file(dir, "sk", s->sk, s->kem->length_secret_key);
	write_file(dir, "ct", s->ct, s->kem->length_ciphertext);
	write_file(dir, "ss", s->ss, s->kem->length_shared_secret);
}

/* Allocate and read only what `op` uses. */
static void *oqs_load(const char *alg, const char *op, const char *dir) {
	oqs_state *s = oqs_new(alg);
	size_t pk_len = s->kem->length_public_key;
	size_t sk_len = s->kem->length_secret_key;
	size_t ct_len = s->kem->length_ciphertext;
	size_t ss_len = s->kem->length_shared_secret;

	if (strcmp(op, "keygen") == 0) {
		s->out_pk = malloc(pk_len);
		s->out_sk = malloc(sk_len);
	} else if (strcmp(op, "encaps") == 0) {
		s->pk = malloc(pk_len);
		s->out_ct = malloc(ct_len);
		s->out_ss = malloc(ss_len);
		if (read_file(dir, "pk", s->pk, pk_len) != pk_len) die("pk has the wrong length");
	} else {
		s->sk = malloc(sk_len);
		s->ct = malloc(ct_len);
		s->out_ss = malloc(ss_len);
		if (read_file(dir, "sk", s->sk, sk_len) != sk_len) die("sk has the wrong length");
		if (read_file(dir, "ct", s->ct, ct_len) != ct_len) die("ct has the wrong length");
	}
	return s;
}

static int oqs_keygen(void *state) {
	oqs_state *s = state;
	return OQS_KEM_keypair(s->kem, s->out_pk, s->out_sk) == OQS_SUCCESS;
}

static int oqs_encaps(void *state) {
	oqs_state *s = state;
	return OQS_KEM_encaps(s->kem, s->out_ct, s->out_ss, s->pk) == OQS_SUCCESS;
}

static int oqs_decaps(void *state) {
	oqs_state *s = state;
	return OQS_KEM_decaps(s->kem, s->out_ss, s->ct, s->sk) == OQS_SUCCESS;
}

static void oqs_cleanup(void *state) { (void)state; }

static size_t oqs_secret(void *state, const uint8_t **ss) {
	oqs_state *s = state;
	*ss = s->out_ss;
	return s->kem->length_shared_secret;
}

static const backend oqs_backend = {
	oqs_init, oqs_save, oqs_load, oqs_keygen, oqs_encaps, oqs_decaps, oqs_cleanup, oqs_secret,
};

/* ================================================================
 * OpenSSL
 *
 * Most algorithms go through OpenSSL's KEM interface
 * (EVP_PKEY_encapsulate / EVP_PKEY_decapsulate): DHKEM for X25519 and
 * P-256, RSASVE for RSA, and ML-KEM natively.
 *
 * Finite-field DH has no KEM in OpenSSL, so ffdhe is mapped by hand:
 *   encaps = generate an ephemeral key, encode its public key, derive
 *   decaps = decode the peer's public key, derive
 *
 * The keygen context and the KEM contexts are created once, in init or
 * load. Saved keys are their raw parameters (EVP_PKEY_todata), loaded
 * back with EVP_PKEY_fromdata, which allocates far less than decoding
 * DER would.
 * ================================================================ */

typedef struct {
	const char *name;
	const char *keytype; /* OpenSSL key type */
	const char *group;   /* named group, for EC and DH */
	const char *kem_op;  /* OSSL_KEM_PARAM_OPERATION, where needed */
	int rsa_bits;
	int ffdh;            /* 1: no KEM interface, use the hand mapping */
} ossl_alg;

static const ossl_alg ossl_algs[] = {
	{.name = "X25519", .keytype = "X25519", .kem_op = "DHKEM"},
	{.name = "P-256", .keytype = "EC", .group = "P-256", .kem_op = "DHKEM"},
	{.name = "RSA-2048", .keytype = "RSA", .kem_op = "RSASVE", .rsa_bits = 2048},
	{.name = "RSA-3072", .keytype = "RSA", .kem_op = "RSASVE", .rsa_bits = 3072},
	{.name = "ffdhe2048", .keytype = "DH", .group = "ffdhe2048", .ffdh = 1},
	{.name = "ffdhe3072", .keytype = "DH", .group = "ffdhe3072", .ffdh = 1},
	{.name = "ML-KEM-512", .keytype = "ML-KEM-512"},
	{.name = "ML-KEM-768", .keytype = "ML-KEM-768"},
	{.name = "ML-KEM-1024", .keytype = "ML-KEM-1024"},
	{0},
};

typedef struct {
	const ossl_alg *alg;
	EVP_PKEY_CTX *keygen_ctx;
	EVP_PKEY *key;                         /* the recipient key */
	EVP_PKEY_CTX *encaps_ctx, *decaps_ctx; /* KEM path only */

	/* reference ciphertext and shared secret */
	unsigned char ct[BUF_MAX], ss[BUF_MAX];
	size_t ct_len, ss_len;

	/* scratch outputs of the operations */
	unsigned char out_ct[BUF_MAX], out_ss[BUF_MAX];
	size_t out_ss_len;

	/* allocated during an operation, freed by cleanup */
	EVP_PKEY *tmp_key;
	EVP_PKEY_CTX *tmp_ctx;
	unsigned char *tmp_buf;
} ossl_state;

static int generate_key(ossl_state *s, EVP_PKEY **out) {
	*out = NULL;
	return EVP_PKEY_generate(s->keygen_ctx, out) == 1;
}

/* --- KEM interface --- */

static int kem_encaps(ossl_state *s, unsigned char *ct, size_t *ct_len, unsigned char *ss, size_t *ss_len) {
	return EVP_PKEY_encapsulate(s->encaps_ctx, ct, ct_len, ss, ss_len) == 1;
}

static int kem_decaps(ossl_state *s, const unsigned char *ct, size_t ct_len, unsigned char *ss, size_t *ss_len) {
	return EVP_PKEY_decapsulate(s->decaps_ctx, ss, ss_len, ct, ct_len) == 1;
}

/* --- finite-field DH, mapped by hand --- */

/* Derive with `priv` against `peer`. The secret is padded to the group
 * size, as TLS 1.3 does, and OpenSSL's default peer-key validation is
 * kept, as TLS keeps it. */
static int ffdh_derive(ossl_state *s, EVP_PKEY *priv, EVP_PKEY *peer, unsigned char *ss, size_t *ss_len) {
	s->tmp_ctx = EVP_PKEY_CTX_new_from_pkey(NULL, priv, NULL);
	return s->tmp_ctx &&
	       EVP_PKEY_derive_init(s->tmp_ctx) == 1 &&
	       EVP_PKEY_CTX_set_dh_pad(s->tmp_ctx, 1) == 1 &&
	       EVP_PKEY_derive_set_peer(s->tmp_ctx, peer) == 1 &&
	       EVP_PKEY_derive(s->tmp_ctx, ss, ss_len) == 1;
}

static int ffdh_encaps(ossl_state *s, unsigned char *ct, size_t *ct_len, unsigned char *ss, size_t *ss_len) {
	if (!generate_key(s, &s->tmp_key)) return 0;
	EVP_PKEY *ephemeral = s->tmp_key;

	size_t n = EVP_PKEY_get1_encoded_public_key(ephemeral, &s->tmp_buf);
	if (n == 0 || n > *ct_len) return 0;
	memcpy(ct, s->tmp_buf, n);
	*ct_len = n;

	return ffdh_derive(s, ephemeral, s->key, ss, ss_len);
}

static int ffdh_decaps(ossl_state *s, const unsigned char *ct, size_t ct_len, unsigned char *ss, size_t *ss_len) {
	s->tmp_key = EVP_PKEY_new();
	EVP_PKEY *peer = s->tmp_key;
	return peer &&
	       EVP_PKEY_copy_parameters(peer, s->key) == 1 &&
	       EVP_PKEY_set1_encoded_public_key(peer, ct, ct_len) == 1 &&
	       ffdh_derive(s, s->key, peer, ss, ss_len);
}

/* --- dispatch between the two paths --- */

static int ossl_encapsulate(ossl_state *s, unsigned char *ct, size_t *ct_len, unsigned char *ss, size_t *ss_len) {
	return s->alg->ffdh ? ffdh_encaps(s, ct, ct_len, ss, ss_len) : kem_encaps(s, ct, ct_len, ss, ss_len);
}

static int ossl_decapsulate(ossl_state *s, const unsigned char *ct, size_t ct_len, unsigned char *ss, size_t *ss_len) {
	return s->alg->ffdh ? ffdh_decaps(s, ct, ct_len, ss, ss_len) : kem_decaps(s, ct, ct_len, ss, ss_len);
}

/* --- operations --- */

static int ossl_keygen(void *state) {
	ossl_state *s = state;
	return generate_key(s, &s->tmp_key);
}

static int ossl_encaps(void *state) {
	ossl_state *s = state;
	size_t ct_len = sizeof s->out_ct;
	s->out_ss_len = sizeof s->out_ss;
	return ossl_encapsulate(s, s->out_ct, &ct_len, s->out_ss, &s->out_ss_len);
}

static int ossl_decaps(void *state) {
	ossl_state *s = state;
	s->out_ss_len = sizeof s->out_ss;
	return ossl_decapsulate(s, s->ct, s->ct_len, s->out_ss, &s->out_ss_len);
}

static void ossl_cleanup(void *state) {
	ossl_state *s = state;
	EVP_PKEY_free(s->tmp_key);
	EVP_PKEY_CTX_free(s->tmp_ctx);
	OPENSSL_free(s->tmp_buf);
	s->tmp_key = NULL;
	s->tmp_ctx = NULL;
	s->tmp_buf = NULL;
}

static size_t ossl_secret(void *state, const uint8_t **ss) {
	ossl_state *s = state;
	*ss = s->out_ss;
	return s->out_ss_len;
}

/* --- setup --- */

static const ossl_alg *find_ossl_alg(const char *name) {
	for (const ossl_alg *a = ossl_algs; a->name; a++)
		if (strcmp(a->name, name) == 0) return a;
	die("unknown OpenSSL algorithm");
	return NULL;
}

static EVP_PKEY_CTX *new_keygen_ctx(const ossl_alg *a) {
	EVP_PKEY_CTX *ctx = EVP_PKEY_CTX_new_from_name(NULL, a->keytype, NULL);
	if (!ctx || EVP_PKEY_keygen_init(ctx) != 1) die("OpenSSL keygen init failed");
	if (a->group && EVP_PKEY_CTX_set_group_name(ctx, a->group) != 1) die("set group failed");
	if (a->rsa_bits && EVP_PKEY_CTX_set_rsa_keygen_bits(ctx, a->rsa_bits) != 1) die("set RSA bits failed");
	return ctx;
}

static EVP_PKEY_CTX *new_kem_ctx(ossl_state *s, int for_encaps) {
	EVP_PKEY_CTX *ctx = EVP_PKEY_CTX_new_from_pkey(NULL, s->key, NULL);
	OSSL_PARAM params[2] = {OSSL_PARAM_END, OSSL_PARAM_END};
	if (s->alg->kem_op)
		params[0] = OSSL_PARAM_construct_utf8_string(OSSL_KEM_PARAM_OPERATION, (char *)s->alg->kem_op, 0);

	int ok = ctx && (for_encaps ? EVP_PKEY_encapsulate_init(ctx, params)
	                            : EVP_PKEY_decapsulate_init(ctx, params)) == 1;
	if (!ok) die("OpenSSL KEM init failed");
	return ctx;
}

/* RSA has no "encoded public key"; report the modulus size instead. */
static size_t public_key_size(EVP_PKEY *key) {
	unsigned char *encoded = NULL;
	size_t n = EVP_PKEY_get1_encoded_public_key(key, &encoded);
	OPENSSL_free(encoded);
	if (n == 0) {
		ERR_clear_error();
		n = (size_t)EVP_PKEY_get_size(key);
	}
	return n;
}

static void *ossl_init(const char *name) {
	ossl_state *s = calloc(1, sizeof *s);
	s->alg = find_ossl_alg(name);
	s->keygen_ctx = new_keygen_ctx(s->alg);
	if (!generate_key(s, &s->key)) die("OpenSSL keygen failed");
	if (!s->alg->ffdh) {
		s->encaps_ctx = new_kem_ctx(s, 1);
		s->decaps_ctx = new_kem_ctx(s, 0);
	}

	/* Round trip: the reference ciphertext, and a correctness check. */
	unsigned char ss_receiver[BUF_MAX];
	size_t ss_receiver_len = sizeof ss_receiver;
	s->ct_len = sizeof s->ct;
	s->ss_len = sizeof s->ss;
	if (!ossl_encapsulate(s, s->ct, &s->ct_len, s->ss, &s->ss_len)) die("OpenSSL setup encaps failed");
	ossl_cleanup(s);
	if (!ossl_decapsulate(s, s->ct, s->ct_len, ss_receiver, &ss_receiver_len)) die("OpenSSL setup decaps failed");
	ossl_cleanup(s);
	if (s->ss_len != ss_receiver_len || memcmp(s->ss, ss_receiver, s->ss_len) != 0)
		die("OpenSSL shared secrets differ");

	print_sizes(public_key_size(s->key), s->ct_len, s->ss_len);
	return s;
}

/* --- saving and loading keys as raw parameters ---
 *
 * File format: a sequence of records
 *   uint32 key_len, key bytes (NUL included),
 *   uint32 data_type, uint32 data_len, data bytes (+ a NUL for strings)
 */

#define PARAMS_FILE_MAX (64 * 1024)
#define PARAMS_MAX 32

static void append(unsigned char *buf, size_t *len, const void *data, size_t n) {
	if (*len + n > PARAMS_FILE_MAX) die("key parameters too large");
	memcpy(buf + *len, data, n);
	*len += n;
}

static void append_u32(unsigned char *buf, size_t *len, uint32_t v) { append(buf, len, &v, sizeof v); }

static void save_key_params(EVP_PKEY *key, int selection, const char *dir, const char *name) {
	OSSL_PARAM *params = NULL;
	if (EVP_PKEY_todata(key, selection, &params) != 1) die("EVP_PKEY_todata failed");

	static unsigned char buf[PARAMS_FILE_MAX];
	size_t len = 0;
	for (const OSSL_PARAM *p = params; p->key; p++) {
		/* With the seed present, ML-KEM would re-derive the key on import. */
		if (strcmp(p->key, "seed") == 0) continue;
		int is_string = p->data_type == OSSL_PARAM_UTF8_STRING;
		append_u32(buf, &len, (uint32_t)strlen(p->key) + 1);
		append(buf, &len, p->key, strlen(p->key) + 1);
		append_u32(buf, &len, p->data_type);
		append_u32(buf, &len, (uint32_t)p->data_size);
		append(buf, &len, p->data, p->data_size);
		if (is_string) append(buf, &len, "", 1);
	}
	OSSL_PARAM_free(params);
	write_file(dir, name, buf, len);
}

static uint32_t take_u32(const unsigned char *buf, size_t len, size_t *pos) {
	uint32_t v;
	if (*pos + sizeof v > len) die("truncated key parameters");
	memcpy(&v, buf + *pos, sizeof v);
	*pos += sizeof v;
	return v;
}

/* Rebuild the key from saved parameters. Uses static storage only. */
static EVP_PKEY *load_key_params(const ossl_alg *a, int selection, const char *dir, const char *name) {
	static unsigned char buf[PARAMS_FILE_MAX];
	static OSSL_PARAM params[PARAMS_MAX + 1];
	size_t len = read_file(dir, name, buf, sizeof buf), pos = 0;
	int n = 0;
	while (pos < len) {
		if (n == PARAMS_MAX) die("too many key parameters");
		uint32_t key_len = take_u32(buf, len, &pos);
		const char *key = (const char *)buf + pos;
		pos += key_len;
		uint32_t type = take_u32(buf, len, &pos);
		uint32_t data_len = take_u32(buf, len, &pos);
		params[n++] = (OSSL_PARAM){key, type, buf + pos, data_len, OSSL_PARAM_UNMODIFIED};
		pos += data_len + (type == OSSL_PARAM_UTF8_STRING ? 1 : 0);
		if (pos > len) die("truncated key parameters");
	}
	params[n] = OSSL_PARAM_construct_end();

	EVP_PKEY *key = NULL;
	EVP_PKEY_CTX *ctx = EVP_PKEY_CTX_new_from_name(NULL, a->keytype, NULL);
	if (!ctx || EVP_PKEY_fromdata_init(ctx) != 1 || EVP_PKEY_fromdata(ctx, &key, selection, params) != 1)
		die("EVP_PKEY_fromdata failed");
	EVP_PKEY_CTX_free(ctx);
	return key;
}

static void ossl_save(void *state, const char *dir) {
	ossl_state *s = state;
	save_key_params(s->key, EVP_PKEY_PUBLIC_KEY, dir, "public.params");
	save_key_params(s->key, EVP_PKEY_KEYPAIR, dir, "keypair.params");
	write_file(dir, "ct", s->ct, s->ct_len);
	write_file(dir, "ss", s->ss, s->ss_len);
}

/* Set up only what `op` uses: a sender holds the recipient's public key,
 * the recipient holds the keypair and a ciphertext. */
static void *ossl_load(const char *name, const char *op, const char *dir) {
	ossl_state *s = calloc(1, sizeof *s);
	s->alg = find_ossl_alg(name);

	if (strcmp(op, "keygen") == 0) {
		s->keygen_ctx = new_keygen_ctx(s->alg);
	} else if (strcmp(op, "encaps") == 0) {
		s->key = load_key_params(s->alg, EVP_PKEY_PUBLIC_KEY, dir, "public.params");
		if (s->alg->ffdh)
			s->keygen_ctx = new_keygen_ctx(s->alg); /* for the ephemeral key */
		else
			s->encaps_ctx = new_kem_ctx(s, 1);
	} else {
		s->key = load_key_params(s->alg, EVP_PKEY_KEYPAIR, dir, "keypair.params");
		if (!s->alg->ffdh) s->decaps_ctx = new_kem_ctx(s, 0);
		s->ct_len = read_file(dir, "ct", s->ct, sizeof s->ct);
	}
	return s;
}

static const backend ossl_backend = {
	ossl_init, ossl_save, ossl_load, ossl_keygen, ossl_encaps, ossl_decaps, ossl_cleanup, ossl_secret,
};

/* ================================================================
 * Command line
 * ================================================================ */

static void usage(void) {
	fprintf(stderr,
	        "usage: kem_bench time     <liboqs|openssl> <alg> <keygen|encaps|decaps> "
	        "<max_iters> <max_seconds> <warmup_seconds>\n"
	        "       kem_bench prepare  <liboqs|openssl> <alg> <dir>\n"
	        "       kem_bench memory   <liboqs|openssl> <alg> <keygen|encaps|decaps> <dir>\n"
	        "       kem_bench once     <liboqs|openssl> <alg> <keygen|encaps|decaps> <dir>\n"
	        "       kem_bench baseline <liboqs|openssl> <alg> <keygen|encaps|decaps> <dir>\n"
	        "       kem_bench version\n");
	exit(2);
}

static const backend *select_backend(const char *impl) {
	if (strcmp(impl, "liboqs") == 0) return &oqs_backend;
	if (strcmp(impl, "openssl") == 0) return &ossl_backend;
	usage();
	return NULL;
}

static int (*select_op(const backend *b, const char *op))(void *) {
	if (strcmp(op, "keygen") == 0) return b->keygen;
	if (strcmp(op, "encaps") == 0) return b->encaps;
	if (strcmp(op, "decaps") == 0) return b->decaps;
	usage();
	return NULL;
}

/* ================================================================
 * time
 * ================================================================ */

typedef struct {
	const backend *backend;
	void *state;
	int (*op)(void *state);
	long max_iters;
	uint64_t max_ns, warmup_ns;
} timing;

typedef struct {
	uint64_t tsc_ticks, ns;
	int64_t perf_cycles; /* -1 without perf */
} sample;

/* Warm caches, branch predictors and lazy initialisation. */
static void warm_up(const timing *t) {
	uint64_t start = now_ns();
	for (long i = 0; i < t->max_iters && now_ns() - start < t->warmup_ns; i++) {
		if (!t->op(t->state)) die("operation failed during warmup");
		t->backend->cleanup(t->state);
	}
}

/* Time the operation into `out` (room for max_iters). Returns the count. */
static long measure(const timing *t, int perf_fd, sample *out) {
	long n = 0;
	uint64_t start = now_ns();
	while (n < t->max_iters && (n < MIN_ITERS || now_ns() - start < t->max_ns)) {
		if (perf_fd >= 0) perf_start(perf_fd);
		uint64_t ns0 = now_ns(), tsc0 = read_tsc();

		int ok = t->op(t->state);

		uint64_t tsc1 = read_tsc(), ns1 = now_ns();
		int64_t cycles = perf_fd >= 0 ? perf_stop(perf_fd) : -1;

		if (!ok) die("operation failed");
		t->backend->cleanup(t->state);
		out[n++] = (sample){.tsc_ticks = tsc1 - tsc0, .ns = ns1 - ns0, .perf_cycles = cycles};
	}
	return n;
}

/* kem_bench time <impl> <alg> <op> <max_iters> <max_seconds> <warmup_seconds> */
static int cmd_time(int argc, char **argv) {
	if (argc != 8) usage();
	timing t = {0};
	t.backend = select_backend(argv[2]);
	t.op = select_op(t.backend, argv[4]);
	t.max_iters = atol(argv[5]);
	t.max_ns = (uint64_t)(atof(argv[6]) * 1e9);
	t.warmup_ns = (uint64_t)(atof(argv[7]) * 1e9);
	if (t.max_iters < MIN_ITERS) die("max_iters below minimum");
	t.state = t.backend->init(argv[3]);

	warm_up(&t);
	int perf_fd = perf_open();
	printf("M,perf,%d\n", perf_fd >= 0);

	sample *samples = malloc(t.max_iters * sizeof *samples);
	long n = measure(&t, perf_fd, samples);
	for (long i = 0; i < n; i++)
		printf("S,%llu,%llu,%lld\n", (unsigned long long)samples[i].tsc_ticks,
		       (unsigned long long)samples[i].ns, (long long)samples[i].perf_cycles);
	return 0;
}

/* ================================================================
 * prepare / once / baseline
 * ================================================================ */

/* kem_bench prepare <impl> <alg> <dir> */
static int cmd_prepare(int argc, char **argv) {
	if (argc != 5) usage();
	const backend *b = select_backend(argv[2]);
	void *state = b->init(argv[3]);
	mkdir(argv[4], 0700);
	b->save(state, argv[4]);
	return 0;
}

/* After decaps, the secret must match the one prepare saved. */
static void check_secret(const backend *b, void *state, const char *dir) {
	static uint8_t expected[BUF_MAX];
	size_t expected_len = read_file(dir, "ss", expected, sizeof expected);
	const uint8_t *got;
	size_t got_len = b->secret(state, &got);
	if (got_len != expected_len || memcmp(got, expected, got_len) != 0)
		die("decapsulated secret differs from the saved one");
}

/* kem_bench once|baseline <impl> <alg> <op> <dir> */
static int cmd_once(int argc, char **argv, int run_op) {
	if (argc != 6) usage();
	const backend *b = select_backend(argv[2]);
	const char *alg = argv[3], *op_name = argv[4], *dir = argv[5];
	int (*op)(void *) = select_op(b, op_name);
	void *state = b->load(alg, op_name, dir);

	if (run_op) {
		if (!op(state)) die("operation failed");
		if (strcmp(op_name, "decaps") == 0) check_secret(b, state, dir);
	}
	_exit(0); /* skip library cleanup: nothing after the operation runs */
}

/* ================================================================
 * memory
 *
 * Stack is measured in every build; heap only in the memory build
 * (-DKEM_MEMORY), whose allocator wrappers would add their own frames to
 * any allocation path and so distort the stack figure. run_memory.py
 * therefore takes stack from the plain build and heap from the memory
 * build.
 * ================================================================ */

#ifdef KEM_MEMORY
/* --- heap: every allocation by the driver, liboqs and libcrypto ---
 *
 * The memory build links with --wrap for each function below, so calls
 * from our objects and from the static liboqs.a and libcrypto.a reach
 * these wrappers. A table maps each live block to its requested size.
 * Allocations glibc makes internally (stdio buffers, for example) do not
 * pass through the wrappers and are not counted. */

void *__real_malloc(size_t);
void *__real_calloc(size_t, size_t);
void *__real_realloc(void *, size_t);
void __real_free(void *);
void *__real_aligned_alloc(size_t, size_t);
int __real_posix_memalign(void **, size_t, size_t);
void *__real_memalign(size_t, size_t);

#define HEAP_SLOTS (1u << 18)
#define TOMBSTONE ((void *)1)

static struct {
	void *ptr;
	size_t size;
} heap_table[HEAP_SLOTS];
static size_t heap_live, heap_peak;

static size_t slot_of(const void *p) {
	uint64_t x = (uint64_t)(uintptr_t)p;
	x ^= x >> 33;
	x *= 0xff51afd7ed558ccdULL;
	x ^= x >> 33;
	return (size_t)x & (HEAP_SLOTS - 1);
}

static void heap_add(void *p, size_t size) {
	if (!p) return;
	for (size_t i = slot_of(p), n = 0; n < HEAP_SLOTS; i = (i + 1) & (HEAP_SLOTS - 1), n++) {
		if (heap_table[i].ptr == NULL || heap_table[i].ptr == TOMBSTONE) {
			heap_table[i].ptr = p;
			heap_table[i].size = size;
			heap_live += size;
			if (heap_live > heap_peak) heap_peak = heap_live;
			return;
		}
	}
	die("heap tracking table full");
}

/* Forget p; returns its size, or 0 for a block we never saw. */
static size_t heap_remove(void *p) {
	if (!p) return 0;
	for (size_t i = slot_of(p), n = 0; n < HEAP_SLOTS && heap_table[i].ptr; i = (i + 1) & (HEAP_SLOTS - 1), n++) {
		if (heap_table[i].ptr == p) {
			size_t size = heap_table[i].size;
			heap_table[i].ptr = TOMBSTONE;
			heap_live -= size;
			return size;
		}
	}
	return 0;
}

void *__wrap_malloc(size_t n) {
	void *p = __real_malloc(n);
	heap_add(p, n);
	return p;
}

void *__wrap_calloc(size_t count, size_t n) {
	void *p = __real_calloc(count, n);
	heap_add(p, count * n);
	return p;
}

void *__wrap_realloc(void *old, size_t n) {
	size_t old_size = heap_remove(old);
	void *p = __real_realloc(old, n);
	if (p) heap_add(p, n);
	else if (old && n) heap_add(old, old_size); /* failed: old block still live */
	return p;
}

void __wrap_free(void *p) {
	heap_remove(p);
	__real_free(p);
}

void *__wrap_aligned_alloc(size_t align, size_t n) {
	void *p = __real_aligned_alloc(align, n);
	heap_add(p, n);
	return p;
}

int __wrap_posix_memalign(void **out, size_t align, size_t n) {
	int rc = __real_posix_memalign(out, align, n);
	if (rc == 0) heap_add(*out, n);
	return rc;
}

void *__wrap_memalign(size_t align, size_t n) {
	void *p = __real_memalign(align, n);
	heap_add(p, n);
	return p;
}

static size_t heap_window_base;

static void heap_window_start(void) {
	heap_window_base = heap_live;
	heap_peak = heap_live;
}

/* Peak live bytes since heap_window_start, above the level then. */
static long heap_window_bytes(void) { return (long)(heap_peak - heap_window_base); }

#else /* !KEM_MEMORY: allocations are not tracked in this build */

static void heap_window_start(void) {}
static long heap_window_bytes(void) { return -1; }

#endif /* KEM_MEMORY */

/* --- stack: run the call on a separate, pattern-filled stack ---
 *
 * The call runs on its own 64 MiB stack (Classic McEliece keygen needs
 * up to ~2 MB), with an inaccessible guard page below it so an overflow
 * crashes instead of giving a wrong answer. Afterwards, the first byte
 * from the bottom that no longer holds the fill pattern marks the
 * deepest point written. Stack that is reserved but never written is
 * not counted. */

#define ALT_STACK_BYTES ((size_t)64 << 20)

static unsigned char *alt_stack; /* usable region, above the guard page */
static ucontext_t caller_ctx, op_ctx;
static int (*stack_op)(void *);
static void *stack_state;
static int stack_op_ok;

static void run_stack_op(void) { stack_op_ok = stack_op(stack_state); }

static void alt_stack_init(void) {
	size_t page = (size_t)sysconf(_SC_PAGESIZE);
	unsigned char *region = mmap(NULL, ALT_STACK_BYTES + page, PROT_READ | PROT_WRITE,
	                             MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
	if (region == MAP_FAILED) die("mmap failed");
	if (mprotect(region, page, PROT_NONE) != 0) die("mprotect failed");
	alt_stack = region + page;
}

/* Run op on the alternate stack; returns the bytes of stack it wrote. */
static size_t stack_used_by(int (*op)(void *), void *state, unsigned char pattern) {
	memset(alt_stack, pattern, ALT_STACK_BYTES);
	stack_op = op;
	stack_state = state;
	if (getcontext(&op_ctx) != 0) die("getcontext failed");
	op_ctx.uc_stack.ss_sp = alt_stack;
	op_ctx.uc_stack.ss_size = ALT_STACK_BYTES;
	op_ctx.uc_link = &caller_ctx;
	makecontext(&op_ctx, run_stack_op, 0);
	if (swapcontext(&caller_ctx, &op_ctx) != 0) die("swapcontext failed");
	if (!stack_op_ok) die("operation failed");

	size_t untouched = 0;
	while (untouched < ALT_STACK_BYTES && alt_stack[untouched] == pattern) untouched++;
	return ALT_STACK_BYTES - untouched;
}

/* The harness's own frames on the alternate stack (the context
 * trampoline, and a call through the backend's function pointer) are
 * measured by running an operation that does nothing, and subtracted. */
static int no_op(void *state) {
	(void)state;
	return 1;
}

static size_t max_size(size_t a, size_t b) { return a > b ? a : b; }
static long max_long(long a, long b) { return a > b ? a : b; }

typedef struct {
	long heap;    /* -1 where this build does not track allocations */
	size_t stack; /* raw: includes the harness overhead */
} mem_usage;

/* One call: its heap peak above the starting level, and its stack. */
static mem_usage measure_call(const backend *b, int (*op)(void *), void *state, unsigned char pattern) {
	heap_window_start();
	size_t stack = stack_used_by(op, state, pattern);
	mem_usage u = {.heap = heap_window_bytes(), .stack = stack};
	b->cleanup(state);
	return u;
}

/* kem_bench memory <impl> <alg> <op> <dir> */
static int cmd_memory(int argc, char **argv) {
	if (argc != 6) usage();
	const backend *b = select_backend(argv[2]);
	const char *alg = argv[3], *op_name = argv[4], *dir = argv[5];
	int (*op)(void *) = select_op(b, op_name);
	alt_stack_init();
	size_t overhead = max_size(stack_used_by(no_op, NULL, 0xA5), stack_used_by(no_op, NULL, 0x5A));
	void *state = b->load(alg, op_name, dir);

	mem_usage first = measure_call(b, op, state, 0xA5);
	if (strcmp(op_name, "decaps") == 0) check_secret(b, state, dir);

	/* Two patterns, so a call that happens to write the fill byte at its
	 * deepest point cannot hide it. */
	mem_usage again1 = measure_call(b, op, state, 0xA5);
	mem_usage again2 = measure_call(b, op, state, 0x5A);
	mem_usage steady = {max_long(again1.heap, again2.heap), max_size(again1.stack, again2.stack)};

	printf("M,first_heap_bytes,%ld\n", first.heap);
	printf("M,first_stack_bytes,%zu\n", first.stack - overhead);
	printf("M,steady_heap_bytes,%ld\n", steady.heap);
	printf("M,steady_stack_bytes,%zu\n", steady.stack - overhead);
	printf("M,stack_overhead_bytes,%zu\n", overhead);
	return 0;
}

int main(int argc, char **argv) {
	if (argc < 2) usage();
	const char *cmd = argv[1];
	if (strcmp(cmd, "version") == 0) {
		printf("liboqs %s\n%s\n", OQS_version(), OpenSSL_version(OPENSSL_VERSION));
		return 0;
	}
	if (strcmp(cmd, "time") == 0) return cmd_time(argc, argv);
	if (strcmp(cmd, "prepare") == 0) return cmd_prepare(argc, argv);
	if (strcmp(cmd, "once") == 0) return cmd_once(argc, argv, 1);
	if (strcmp(cmd, "baseline") == 0) return cmd_once(argc, argv, 0);
	if (strcmp(cmd, "memory") == 0) return cmd_memory(argc, argv);
	usage();
}
