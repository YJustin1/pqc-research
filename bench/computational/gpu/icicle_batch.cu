// Batched ML-KEM on the GPU through ICICLE's own API, against single-thread
// CPU ML-KEM from liboqs' native build. Run by run_gpu.py, which builds it.
//
//     icicle_batch <set> <max_batch> <reps> <max_seconds>
//
// Prints CSV lines:
//     C,<set>,<check>,<ok|FAIL>,<detail>       GPU output checked against the CPU
//     P,<probe>,<rep>,<ns>                      fixed per-call GPU costs
//     G,<set>,<op>,<host|device>,<batch>,<rep>,<ns>   one timed GPU call
//     U,<set>,<op>,<rep>,<ns>                   one timed CPU operation
//
// host mode: inputs and outputs in host memory, so each call includes
// ICICLE's device allocations and both copies. device mode: everything
// already on the GPU. Every call is followed by a device synchronise, and
// the set runs keep CUDA's memory pool (see keep_pool). Exits non-zero if
// any check fails.

#include <cuda_runtime.h>
#include <oqs/oqs.h>

#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <string>
#include <vector>

#include "icicle/pqc/ml_kem.h"

namespace mlkem = icicle::pqc::ml_kem;

static uint64_t now_ns() {
	timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return (uint64_t)ts.tv_sec * 1000000000u + (uint64_t)ts.tv_nsec;
}

static void cuda_ok(cudaError_t err, const char *what) {
	if (err != cudaSuccess) {
		fprintf(stderr, "ERROR: %s: %s\n", what, cudaGetErrorString(err));
		exit(1);
	}
}

static void icicle_ok(icicle::eIcicleError err, const char *what) {
	if (err != icicle::eIcicleError::SUCCESS) {
		fprintf(stderr, "ERROR: ICICLE %s failed (%d)\n", what, (int)err);
		exit(1);
	}
}

// liboqs' derandomised entry points: same seeds as ICICLE's entropy and
// message buffers, so outputs must match byte for byte.
struct CpuKem {
	OQS_STATUS (*keypair_derand)(uint8_t *, uint8_t *, const uint8_t *);
	OQS_STATUS (*encaps_derand)(uint8_t *, uint8_t *, const uint8_t *, const uint8_t *);
	OQS_STATUS (*decaps)(uint8_t *, const uint8_t *, const uint8_t *);
};

template <typename P> struct Set;
template <> struct Set<mlkem::Kyber512Params> {
	static constexpr CpuKem cpu = {OQS_KEM_ml_kem_512_keypair_derand, OQS_KEM_ml_kem_512_encaps_derand,
	                               OQS_KEM_ml_kem_512_decaps};
};
template <> struct Set<mlkem::Kyber768Params> {
	static constexpr CpuKem cpu = {OQS_KEM_ml_kem_768_keypair_derand, OQS_KEM_ml_kem_768_encaps_derand,
	                               OQS_KEM_ml_kem_768_decaps};
};
template <> struct Set<mlkem::Kyber1024Params> {
	static constexpr CpuKem cpu = {OQS_KEM_ml_kem_1024_keypair_derand, OQS_KEM_ml_kem_1024_encaps_derand,
	                               OQS_KEM_ml_kem_1024_decaps};
};

static std::byte *B(std::vector<uint8_t> &v) { return reinterpret_cast<std::byte *>(v.data()); }
static std::byte *D(void *p) { return reinterpret_cast<std::byte *>(p); }

// Buffers for a batch of n, on the host and (for device mode) on the GPU.
template <typename P> struct Buffers {
	size_t n;
	std::vector<uint8_t> entropy, msg, pk, sk, ct, ss_e, ss_d;
	void *d_entropy, *d_msg, *d_pk, *d_sk, *d_ct, *d_ss;

	explicit Buffers(size_t n_)
	    : n(n_), entropy(n * mlkem::ENTROPY_BYTES), msg(n * mlkem::MESSAGE_BYTES), pk(n * P::PUBLIC_KEY_BYTES),
	      sk(n * P::SECRET_KEY_BYTES), ct(n * P::CIPHERTEXT_BYTES), ss_e(n * P::SHARED_SECRET_BYTES),
	      ss_d(n * P::SHARED_SECRET_BYTES) {
		OQS_randombytes(entropy.data(), entropy.size());
		OQS_randombytes(msg.data(), msg.size());
		cuda_ok(cudaMalloc(&d_entropy, entropy.size()), "cudaMalloc");
		cuda_ok(cudaMalloc(&d_msg, msg.size()), "cudaMalloc");
		cuda_ok(cudaMalloc(&d_pk, pk.size()), "cudaMalloc");
		cuda_ok(cudaMalloc(&d_sk, sk.size()), "cudaMalloc");
		cuda_ok(cudaMalloc(&d_ct, ct.size()), "cudaMalloc");
		cuda_ok(cudaMalloc(&d_ss, ss_e.size()), "cudaMalloc");
		cuda_ok(cudaMemcpy(d_entropy, entropy.data(), entropy.size(), cudaMemcpyHostToDevice), "copy");
		cuda_ok(cudaMemcpy(d_msg, msg.data(), msg.size(), cudaMemcpyHostToDevice), "copy");
	}
	~Buffers() {
		for (void *p : {d_entropy, d_msg, d_pk, d_sk, d_ct, d_ss}) cudaFree(p);
	}
	Buffers(const Buffers &) = delete;
	Buffers &operator=(const Buffers &) = delete;
};

static mlkem::MlKemConfig config(size_t n, bool device) {
	mlkem::MlKemConfig c;
	c.batch_size = n;
	c.messages_on_device = c.entropy_on_device = c.public_keys_on_device = device;
	c.secret_keys_on_device = c.ciphertexts_on_device = c.shared_secrets_on_device = device;
	return c;
}

// One batched GPU call. Host mode reads and writes the host vectors;
// device mode the device copies.
template <typename P> static void gpu_op(Buffers<P> &b, const char *op, bool device) {
	mlkem::MlKemConfig c = config(b.n, device);
	if (strcmp(op, "keygen") == 0) {
		icicle_ok(device ? mlkem::keygen<P>(D(b.d_entropy), c, D(b.d_pk), D(b.d_sk))
		                 : mlkem::keygen<P>(B(b.entropy), c, B(b.pk), B(b.sk)),
		          "keygen");
	} else if (strcmp(op, "encaps") == 0) {
		icicle_ok(device ? mlkem::encapsulate<P>(D(b.d_msg), D(b.d_pk), c, D(b.d_ct), D(b.d_ss))
		                 : mlkem::encapsulate<P>(B(b.msg), B(b.pk), c, B(b.ct), B(b.ss_e)),
		          "encapsulate");
	} else {
		icicle_ok(device ? mlkem::decapsulate<P>(D(b.d_sk), D(b.d_ct), c, D(b.d_ss))
		                 : mlkem::decapsulate<P>(B(b.sk), B(b.ct), c, B(b.ss_d)),
		          "decapsulate");
	}
	// ICICLE synchronises only when is_async is set (cuda_pqc_ml_kem.cu),
	// so with device buffers the call can return before the kernel ends.
	cuda_ok(cudaDeviceSynchronize(), "synchronize");
}

static bool fail = false;

static void report(const char *set, const char *check, bool ok, const std::string &detail) {
	printf("C,%s,%s,%s,%s\n", set, check, ok ? "ok" : "FAIL", detail.c_str());
	if (!ok) fail = true;
}

// GPU keygen, encaps and decaps of a batch, each compared with liboqs on
// the CPU from the same seeds.
template <typename P> static void check(const char *set, size_t n) {
	const CpuKem &cpu = Set<P>::cpu;
	Buffers<P> b(n);
	gpu_op(b, "keygen", false);
	gpu_op(b, "encaps", false);
	gpu_op(b, "decaps", false);

	std::vector<uint8_t> pk(P::PUBLIC_KEY_BYTES), sk(P::SECRET_KEY_BYTES), ct(P::CIPHERTEXT_BYTES),
	    ss(P::SHARED_SECRET_BYTES);
	size_t bad_keys = 0, bad_encaps = 0, bad_decaps = 0, bad_cpu_decaps = 0;
	for (size_t i = 0; i < n; i++) {
		cpu.keypair_derand(pk.data(), sk.data(), &b.entropy[i * mlkem::ENTROPY_BYTES]);
		bad_keys += memcmp(pk.data(), &b.pk[i * P::PUBLIC_KEY_BYTES], pk.size()) != 0 ||
		            memcmp(sk.data(), &b.sk[i * P::SECRET_KEY_BYTES], sk.size()) != 0;
		cpu.encaps_derand(ct.data(), ss.data(), &b.pk[i * P::PUBLIC_KEY_BYTES], &b.msg[i * mlkem::MESSAGE_BYTES]);
		bad_encaps += memcmp(ct.data(), &b.ct[i * P::CIPHERTEXT_BYTES], ct.size()) != 0 ||
		              memcmp(ss.data(), &b.ss_e[i * P::SHARED_SECRET_BYTES], ss.size()) != 0;
		bad_decaps += memcmp(&b.ss_e[i * P::SHARED_SECRET_BYTES], &b.ss_d[i * P::SHARED_SECRET_BYTES], ss.size()) != 0;
		cpu.decaps(ss.data(), &b.ct[i * P::CIPHERTEXT_BYTES], &b.sk[i * P::SECRET_KEY_BYTES]);
		bad_cpu_decaps += memcmp(ss.data(), &b.ss_e[i * P::SHARED_SECRET_BYTES], ss.size()) != 0;
	}
	auto detail = [n](size_t bad) { return std::to_string(n - bad) + "/" + std::to_string(n) + " match"; };
	report(set, "keygen_equals_cpu", bad_keys == 0, detail(bad_keys));
	report(set, "encaps_equals_cpu", bad_encaps == 0, detail(bad_encaps));
	report(set, "decaps_recovers_secret", bad_decaps == 0, detail(bad_decaps));
	report(set, "cpu_decaps_of_gpu_ciphertext", bad_cpu_decaps == 0, detail(bad_cpu_decaps));

	// Device mode must give the same results as host mode.
	gpu_op(b, "keygen", true);
	gpu_op(b, "encaps", true);
	std::vector<uint8_t> d_ct(b.ct.size());
	cuda_ok(cudaMemcpy(d_ct.data(), b.d_ct, d_ct.size(), cudaMemcpyDeviceToHost), "copy");
	report(set, "device_mode_equals_host_mode", d_ct == b.ct, "ciphertexts of the whole batch");
}

__global__ void empty_kernel() {}

// ICICLE takes its scratch and staging buffers from cudaMallocAsync on
// every call. CUDA's default pool has a release threshold of 0, so each
// synchronise hands that memory back and the next call allocates afresh.
// Keeping it is what a long-running server would configure.
static void keep_pool() {
	cudaMemPool_t pool;
	cuda_ok(cudaDeviceGetDefaultMemPool(&pool, 0), "cudaDeviceGetDefaultMemPool");
	uint64_t threshold = UINT64_MAX;
	cuda_ok(cudaMemPoolSetAttribute(pool, cudaMemPoolAttrReleaseThreshold, &threshold), "cudaMemPoolSetAttribute");
}

// Fixed costs any single GPU operation pays, independent of ML-KEM, and
// one ML-KEM-768 keygen call before and after keep_pool().
static void probes(int reps) {
	{
		Buffers<mlkem::Kyber768Params> b(1);
		for (const char *pool : {"default_pool", "pool_kept"}) {
			if (strcmp(pool, "pool_kept") == 0) keep_pool();
			for (int warm = 0; warm < 10; warm++) gpu_op(b, "keygen", false);
			for (int r = 0; r < reps; r++) {
				uint64_t t0 = now_ns();
				gpu_op(b, "keygen", false);
				printf("P,icicle_768_keygen_%s,%d,%llu\n", pool, r, (unsigned long long)(now_ns() - t0));
			}
		}
	}

	void *d;
	std::vector<uint8_t> h(1024);
	cuda_ok(cudaMalloc(&d, h.size()), "cudaMalloc");
	for (int warm = 0; warm < 10; warm++) {
		empty_kernel<<<1, 1>>>();
		cuda_ok(cudaDeviceSynchronize(), "synchronize");
	}
	for (int r = 0; r < reps; r++) {
		uint64_t t0 = now_ns();
		empty_kernel<<<1, 1>>>();
		cuda_ok(cudaDeviceSynchronize(), "synchronize");
		uint64_t t1 = now_ns();
		cuda_ok(cudaMemcpy(d, h.data(), h.size(), cudaMemcpyHostToDevice), "copy");
		cuda_ok(cudaMemcpy(h.data(), d, h.size(), cudaMemcpyDeviceToHost), "copy");
		uint64_t t2 = now_ns();
		void *p;
		cuda_ok(cudaMalloc(&p, 4096), "cudaMalloc");
		cuda_ok(cudaFree(p), "cudaFree");
		uint64_t t3 = now_ns();
		printf("P,launch_and_sync,%d,%llu\n", r, (unsigned long long)(t1 - t0));
		printf("P,copy_1KiB_round_trip,%d,%llu\n", r, (unsigned long long)(t2 - t1));
		printf("P,malloc_free_4KiB,%d,%llu\n", r, (unsigned long long)(t3 - t2));
	}
	cudaFree(d);
}

static const char *const OPS[] = {"keygen", "encaps", "decaps"};

// Each timed loop runs up to its rep count, stopping early once max_ns
// has passed (after at least 3 reps).
template <typename P> static void run_set(const char *set, size_t max_batch, int reps, uint64_t max_ns) {
	check<P>(set, 256);
	if (fail) return;

	// Single-thread CPU reference, one operation per call.
	{
		const CpuKem &cpu = Set<P>::cpu;
		std::vector<uint8_t> seed(64), pk(P::PUBLIC_KEY_BYTES), sk(P::SECRET_KEY_BYTES), ct(P::CIPHERTEXT_BYTES),
		    ss(P::SHARED_SECRET_BYTES);
		OQS_randombytes(seed.data(), seed.size());
		cpu.keypair_derand(pk.data(), sk.data(), seed.data());
		cpu.encaps_derand(ct.data(), ss.data(), pk.data(), seed.data());
		for (const char *op : OPS) {
			auto call = [&] {
				if (op == OPS[0]) cpu.keypair_derand(pk.data(), sk.data(), seed.data());
				else if (op == OPS[1]) cpu.encaps_derand(ct.data(), ss.data(), pk.data(), seed.data());
				else cpu.decaps(ss.data(), ct.data(), sk.data());
			};
			for (int warm = 0; warm < 100; warm++) call();
			uint64_t start = now_ns();
			for (int r = 0; r < 20 * reps; r++) {
				if (r >= 3 && now_ns() - start > max_ns) break;
				uint64_t t0 = now_ns();
				call();
				printf("U,%s,%s,%d,%llu\n", set, op, r, (unsigned long long)(now_ns() - t0));
			}
		}
	}

	for (size_t n = 1; n <= max_batch; n *= 2) {
		Buffers<P> b(n);
		// Fill pk/sk/ct on both sides so encaps and decaps have real inputs.
		gpu_op(b, "keygen", false);
		gpu_op(b, "encaps", false);
		cuda_ok(cudaMemcpy(b.d_pk, b.pk.data(), b.pk.size(), cudaMemcpyHostToDevice), "copy");
		cuda_ok(cudaMemcpy(b.d_sk, b.sk.data(), b.sk.size(), cudaMemcpyHostToDevice), "copy");
		cuda_ok(cudaMemcpy(b.d_ct, b.ct.data(), b.ct.size(), cudaMemcpyHostToDevice), "copy");
		for (bool device : {false, true}) {
			for (const char *op : OPS) {
				for (int warm = 0; warm < 3; warm++) gpu_op(b, op, device);
				uint64_t start = now_ns();
				for (int r = 0; r < reps; r++) {
					if (r >= 3 && now_ns() - start > max_ns) break;
					uint64_t t0 = now_ns();
					gpu_op(b, op, device);
					printf("G,%s,%s,%s,%zu,%d,%llu\n", set, op, device ? "device" : "host", n, r,
					       (unsigned long long)(now_ns() - t0));
				}
			}
		}
		fflush(stdout);
	}
}

int main(int argc, char **argv) {
	if (argc != 5) {
		fprintf(stderr, "usage: icicle_batch <ML-KEM-512|ML-KEM-768|ML-KEM-1024|probes> "
		                "<max_batch> <reps> <max_seconds>\n");
		return 2;
	}
	const std::string set = argv[1];
	size_t max_batch = strtoull(argv[2], nullptr, 10);
	int reps = atoi(argv[3]);
	uint64_t max_ns = (uint64_t)(atof(argv[4]) * 1e9);

	OQS_init();
	if (set != "probes") keep_pool();
	if (set == "probes") probes(reps);
	else if (set == "ML-KEM-512") run_set<mlkem::Kyber512Params>(argv[1], max_batch, reps, max_ns);
	else if (set == "ML-KEM-768") run_set<mlkem::Kyber768Params>(argv[1], max_batch, reps, max_ns);
	else if (set == "ML-KEM-1024") run_set<mlkem::Kyber1024Params>(argv[1], max_batch, reps, max_ns);
	else {
		fprintf(stderr, "unknown set %s\n", argv[1]);
		return 2;
	}
	OQS_destroy();
	return fail ? 1 : 0;
}
