// THE LAST SIN: The Sin-Eater - M1
// Minimal assertion framework for the standalone core-logic tests.
// Compiled with g++ here AND on the CI runner (ubuntu-latest).

#pragma once

#include <cstdio>
#include <cstdlib>
#include <functional>
#include <string>
#include <vector>

namespace tls_test
{

struct Stats
{
        int Passed = 0;
        int Failed = 0;
        std::vector<std::string> Failures;
};

inline Stats& GetStats()
{
        static Stats S;
        return S;
}

inline void Check(bool bCond, const char* Expr, const char* File, int Line, const std::string& Context = "")
{
        if (bCond)
        {
                ++GetStats().Passed;
        }
        else
        {
                ++GetStats().Failed;
                char Buf[512];
                std::snprintf(Buf, sizeof(Buf), "%s:%d  CHECK(%s) failed", File, Line, Expr);
                std::string Msg = Buf;
                if (!Context.empty()) { Msg += "  [ " + Context + " ]"; }
                GetStats().Failures.push_back(Msg);
                std::printf("  FAIL %s\n", Msg.c_str());
        }
}

inline void Section(const char* Name)
{
        std::printf("\n=== %s ===\n", Name);
}

inline int ReportAndExit()
{
        Stats& S = GetStats();
        std::printf("\n========================================================\n");
        std::printf("TLS CORE-LOGIC TESTS: %d passed, %d failed\n", S.Passed, S.Failed);
        for (const std::string& F : S.Failures) { std::printf("  ! %s\n", F.c_str()); }
        std::printf("========================================================\n");
        return S.Failed == 0 ? 0 : 1;
}

} // namespace tls_test

#define TLS_CHECK(cond) tls_test::Check((cond), #cond, __FILE__, __LINE__)
#define TLS_CHECK_MSG(cond, ctx) tls_test::Check((cond), #cond, __FILE__, __LINE__, (ctx))
#define TLS_SECTION(name) tls_test::Section(name)

// Reads a whole file (test-side I/O only - the core itself is file-free).
inline bool ReadFileToString(const std::string& Path, std::string& Out)
{
        FILE* F = std::fopen(Path.c_str(), "rb");
        if (!F) { return false; }
        std::fseek(F, 0, SEEK_END);
        const long Size = std::ftell(F);
        std::fseek(F, 0, SEEK_SET);
        Out.resize(static_cast<size_t>(Size));
        const size_t Read = Size > 0 ? std::fread(&Out[0], 1, static_cast<size_t>(Size), F) : 0;
        std::fclose(F);
        return Read == static_cast<size_t>(Size);
}
