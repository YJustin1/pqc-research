/*
 * kem_bench: time one KEM operation, through either liboqs or OpenSSL,
 * with the same loop and the same counters for both.
 *
 *   kem_bench <impl> <alg> <op> <max_iters> <max_seconds> <warmup_seconds>
 *   kem_bench version
 *
 *   impl  liboqs | openssl
 *   op    keygen | encaps | decaps
 *
 * Each process:
 *   1. sets up the algorithm, generates one keypair, encapsulates to it,
 *      decapsulates, and checks that both sides got the same secret;
 *   2. warms up by running the operation for warmup_seconds;
 *   3. times the operation until max_iters iterations, or until
 *      max_seconds have passed and at least MIN_ITERS have run.
 *
 * encaps and decaps reuse the keypair (and ciphertext) from step 1.
 * Work that is not the operation itself, such as freeing an OpenSSL key
 * object, happens outside the timed window.
 *
 * Output on stdout, one record per line:
 *   M,<key>,<value>                          metadata
 *   S,<tsc_ticks>,<ns>,<perf_user_cycles>    one per timed iteration;
 *                                            cycles are -1 without perf
 */
#define _GNU_SOURCE
#include <linux/perf_event.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/syscall.h>
#include <time.h>
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
 * Counters
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
 * Each backend's init() does step 1 above and returns its state. The
 * three operations return 1 on success. cleanup() runs after every
 * operation, outside the timed window.
 * ================================================================ */

typedef struct {
	void *(*init)(const char *alg);
	int (*keygen)(void *state);
	int (*encaps)(void *state);
	int (*decaps)(void *state);
	void (*cleanup)(void *state);
} backend;

/* ================================================================
 * liboqs
 *
 * Caller-allocated buffers; the harness allocates nothing per call.
 * ================================================================ */

typedef struct {
	OQS_KEM *kem;
	/* reference keypair and ciphertext, from init */
	uint8_t *pk, *sk, *ct;
	/* scratch outputs of the timed operations */
	uint8_t *out_pk, *out_sk, *out_ct, *out_ss;
} oqs_state;

static void *oqs_init(const char *alg) {
	OQS_init();
	oqs_state *s = calloc(1, sizeof *s);
	s->kem = OQS_KEM_new(alg);
	if (!s->kem) die("liboqs does not know this algorithm, or it is disabled");

	size_t pk_len = s->kem->length_public_key;
	size_t sk_len = s->kem->length_secret_key;
	size_t ct_len = s->kem->length_ciphertext;
	size_t ss_len = s->kem->length_shared_secret;
	s->pk = malloc(pk_len);
	s->sk = malloc(sk_len);
	s->ct = malloc(ct_len);
	s->out_pk = malloc(pk_len);
	s->out_sk = malloc(sk_len);
	s->out_ct = malloc(ct_len);
	s->out_ss = malloc(ss_len);

	uint8_t *ss_sender = malloc(ss_len), *ss_receiver = malloc(ss_len);
	if (OQS_KEM_keypair(s->kem, s->pk, s->sk) != OQS_SUCCESS ||
	    OQS_KEM_encaps(s->kem, s->ct, ss_sender, s->pk) != OQS_SUCCESS ||
	    OQS_KEM_decaps(s->kem, ss_receiver, s->ct, s->sk) != OQS_SUCCESS)
		die("liboqs setup failed");
	if (memcmp(ss_sender, ss_receiver, ss_len) != 0) die("liboqs shared secrets differ");
	free(ss_sender);
	free(ss_receiver);

	print_sizes(pk_len, ct_len, ss_len);
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

static const backend oqs_backend = {oqs_init, oqs_keygen, oqs_encaps, oqs_decaps, oqs_cleanup};

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
 * The keygen context and the KEM contexts are created once, in init.
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
	EVP_PKEY *key;                       /* the recipient keypair */
	EVP_PKEY_CTX *encaps_ctx, *decaps_ctx; /* KEM path only */

	unsigned char ct[BUF_MAX];           /* reference ciphertext, from init */
	size_t ct_len;

	/* scratch outputs of the timed operations */
	unsigned char out_ct[BUF_MAX], out_ss[BUF_MAX];

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

/* --- timed operations --- */

static int ossl_keygen(void *state) {
	ossl_state *s = state;
	return generate_key(s, &s->tmp_key);
}

static int ossl_encaps(void *state) {
	ossl_state *s = state;
	size_t ct_len = sizeof s->out_ct, ss_len = sizeof s->out_ss;
	return ossl_encapsulate(s, s->out_ct, &ct_len, s->out_ss, &ss_len);
}

static int ossl_decaps(void *state) {
	ossl_state *s = state;
	size_t ss_len = sizeof s->out_ss;
	return ossl_decapsulate(s, s->ct, s->ct_len, s->out_ss, &ss_len);
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
	unsigned char ss_sender[BUF_MAX], ss_receiver[BUF_MAX];
	size_t ss_sender_len = sizeof ss_sender, ss_receiver_len = sizeof ss_receiver;
	s->ct_len = sizeof s->ct;
	if (!ossl_encapsulate(s, s->ct, &s->ct_len, ss_sender, &ss_sender_len)) die("OpenSSL setup encaps failed");
	ossl_cleanup(s);
	if (!ossl_decapsulate(s, s->ct, s->ct_len, ss_receiver, &ss_receiver_len)) die("OpenSSL setup decaps failed");
	ossl_cleanup(s);
	if (ss_sender_len != ss_receiver_len || memcmp(ss_sender, ss_receiver, ss_sender_len) != 0)
		die("OpenSSL shared secrets differ");

	print_sizes(public_key_size(s->key), s->ct_len, ss_sender_len);
	return s;
}

static const backend ossl_backend = {ossl_init, ossl_keygen, ossl_encaps, ossl_decaps, ossl_cleanup};

/* ================================================================
 * Measurement
 * ================================================================ */

typedef struct {
	const backend *backend;
	void *state;
	int (*op)(void *state);
	long max_iters;
	uint64_t max_ns, warmup_ns;
} options;

typedef struct {
	uint64_t tsc_ticks, ns;
	int64_t perf_cycles; /* -1 without perf */
} sample;

static void usage(void) {
	fprintf(stderr, "usage: kem_bench <liboqs|openssl> <alg> <keygen|encaps|decaps> "
	                "<max_iters> <max_seconds> <warmup_seconds>\n"
	                "       kem_bench version\n");
	exit(2);
}

static options parse_args(int argc, char **argv) {
	if (argc != 7) usage();
	const char *impl = argv[1], *alg = argv[2], *op = argv[3];
	options o = {0};

	if (strcmp(impl, "liboqs") == 0) o.backend = &oqs_backend;
	else if (strcmp(impl, "openssl") == 0) o.backend = &ossl_backend;
	else usage();

	if (strcmp(op, "keygen") == 0) o.op = o.backend->keygen;
	else if (strcmp(op, "encaps") == 0) o.op = o.backend->encaps;
	else if (strcmp(op, "decaps") == 0) o.op = o.backend->decaps;
	else usage();

	o.max_iters = atol(argv[4]);
	o.max_ns = (uint64_t)(atof(argv[5]) * 1e9);
	o.warmup_ns = (uint64_t)(atof(argv[6]) * 1e9);
	if (o.max_iters < MIN_ITERS) die("max_iters below minimum");

	o.state = o.backend->init(alg);
	return o;
}

/* Warm caches, branch predictors and lazy initialisation. */
static void warm_up(const options *o) {
	uint64_t start = now_ns();
	for (long i = 0; i < o->max_iters && now_ns() - start < o->warmup_ns; i++) {
		if (!o->op(o->state)) die("operation failed during warmup");
		o->backend->cleanup(o->state);
	}
}

/* Time the operation into `out` (room for max_iters). Returns the count. */
static long measure(const options *o, int perf_fd, sample *out) {
	long n = 0;
	uint64_t start = now_ns();
	while (n < o->max_iters && (n < MIN_ITERS || now_ns() - start < o->max_ns)) {
		if (perf_fd >= 0) perf_start(perf_fd);
		uint64_t ns0 = now_ns(), tsc0 = read_tsc();

		int ok = o->op(o->state);

		uint64_t tsc1 = read_tsc(), ns1 = now_ns();
		int64_t cycles = perf_fd >= 0 ? perf_stop(perf_fd) : -1;

		if (!ok) die("operation failed");
		o->backend->cleanup(o->state);
		out[n++] = (sample){.tsc_ticks = tsc1 - tsc0, .ns = ns1 - ns0, .perf_cycles = cycles};
	}
	return n;
}

int main(int argc, char **argv) {
	if (argc == 2 && strcmp(argv[1], "version") == 0) {
		printf("liboqs %s\n%s\n", OQS_version(), OpenSSL_version(OPENSSL_VERSION));
		return 0;
	}

	options o = parse_args(argc, argv);
	warm_up(&o);

	int perf_fd = perf_open();
	printf("M,perf,%d\n", perf_fd >= 0);

	sample *samples = malloc(o.max_iters * sizeof *samples);
	long n = measure(&o, perf_fd, samples);

	for (long i = 0; i < n; i++)
		printf("S,%llu,%llu,%lld\n", (unsigned long long)samples[i].tsc_ticks,
		       (unsigned long long)samples[i].ns, (long long)samples[i].perf_cycles);
	return 0;
}
