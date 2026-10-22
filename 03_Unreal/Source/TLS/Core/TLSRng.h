// THE LAST SIN: The Sin-Eater - M2
// TLSRng: a tiny deterministic PRNG (splitmix64) for the simulation core.
// Pure C++17, header-only. The full 64-bit state serializes into saves so a
// loaded world continues with exactly the random stream it would have had.
// No engine includes, no time-based seeding anywhere in the core.

#pragma once

#include <cstdint>

namespace tls
{

// Fixed seed for every NewGame - the simulation stream is part of the
// deterministic world contract (M2.2 persists it in saves).
constexpr std::uint64_t kDefaultSimSeed = 0x544C532D4D322021ULL;   // "TLS-M2 !"

class Rng
{
public:
        explicit Rng(std::uint64_t Seed = kDefaultSimSeed) : State(Seed) {}

        void Seed(std::uint64_t S) { State = S; }
        std::uint64_t State64() const { return State; }
        void SetState(std::uint64_t S) { State = S; }

        std::uint64_t NextU64()
        {
                std::uint64_t Z = (State += 0x9E3779B97F4A7C15ULL);
                Z = (Z ^ (Z >> 30)) * 0xBF58476D1CE4E5B9ULL;
                Z = (Z ^ (Z >> 27)) * 0x94D049BB133111EBULL;
                return Z ^ (Z >> 31);
        }

        // uniform in [0, 1)
        double NextUnit()
        {
                return static_cast<double>(NextU64() >> 11) * (1.0 / 9007199254740992.0);
        }

        // true with probability P
        bool Chance(double P)
        {
                if (P >= 1.0) { return true; }
                if (P <= 0.0) { return false; }
                return NextUnit() < P;
        }

private:
        std::uint64_t State;
};

} // namespace tls
