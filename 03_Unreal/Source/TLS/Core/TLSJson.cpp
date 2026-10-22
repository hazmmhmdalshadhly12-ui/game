// THE LAST SIN: The Sin-Eater - M1
// TLSJson.cpp - recursive-descent JSON parser + deterministic serializer.
// Error strategy: no exceptions; failures return a JsonParseResult with a
// message and 1-based line/column (UE builds with exceptions disabled).

#include "TLSJson.h"

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>

namespace tls
{

namespace
{

struct Parser
{
        const std::string& Text;
        size_t Pos = 0;
        int Line = 1;
        int Col = 1;

        explicit Parser(const std::string& InText) : Text(InText) {}

        bool AtEnd() const { return Pos >= Text.size(); }
        char Peek() const { return Pos < Text.size() ? Text[Pos] : '\0'; }
        char PeekAt(size_t Offset) const { return Pos + Offset < Text.size() ? Text[Pos + Offset] : '\0'; }

        void Advance()
        {
                if (Pos < Text.size())
                {
                        if (Text[Pos] == '\n') { ++Line; Col = 1; }
                        else { ++Col; }
                        ++Pos;
                }
        }

        void SkipWhitespace()
        {
                while (!AtEnd())
                {
                        const char C = Peek();
                        if (C == ' ' || C == '\t' || C == '\n' || C == '\r') { Advance(); }
                        else { break; }
                }
        }

        bool Fail(const std::string& Message, JsonParseResult& Out)
        {
                Out.Ok = false;
                Out.Error = Message;
                Out.Line = Line;
                Out.Column = Col;
                return false;
        }

        void AppendUtf8(std::string& Out, unsigned int CodePoint)
        {
                if (CodePoint < 0x80)
                {
                        Out.push_back(static_cast<char>(CodePoint));
                }
                else if (CodePoint < 0x800)
                {
                        Out.push_back(static_cast<char>(0xC0 | (CodePoint >> 6)));
                        Out.push_back(static_cast<char>(0x80 | (CodePoint & 0x3F)));
                }
                else if (CodePoint < 0x10000)
                {
                        Out.push_back(static_cast<char>(0xE0 | (CodePoint >> 12)));
                        Out.push_back(static_cast<char>(0x80 | ((CodePoint >> 6) & 0x3F)));
                        Out.push_back(static_cast<char>(0x80 | (CodePoint & 0x3F)));
                }
                else
                {
                        Out.push_back(static_cast<char>(0xF0 | (CodePoint >> 18)));
                        Out.push_back(static_cast<char>(0x80 | ((CodePoint >> 12) & 0x3F)));
                        Out.push_back(static_cast<char>(0x80 | ((CodePoint >> 6) & 0x3F)));
                        Out.push_back(static_cast<char>(0x80 | (CodePoint & 0x3F)));
                }
        }

        bool ParseHex4(unsigned int& Out)
        {
                unsigned int Value = 0;
                for (int I = 0; I < 4; ++I)
                {
                        const char C = Peek();
                        unsigned int Digit = 0;
                        if (C >= '0' && C <= '9') { Digit = static_cast<unsigned int>(C - '0'); }
                        else if (C >= 'a' && C <= 'f') { Digit = static_cast<unsigned int>(C - 'a') + 10; }
                        else if (C >= 'A' && C <= 'F') { Digit = static_cast<unsigned int>(C - 'A') + 10; }
                        else { return false; }
                        Value = (Value << 4) | Digit;
                        Advance();
                }
                Out = Value;
                return true;
            }

        bool ParseString(std::string& Out, JsonParseResult& Result)
        {
                if (Peek() != '"') { return Fail("expected string starting with '\"'", Result); }
                Advance();
                while (!AtEnd())
                {
                        const char C = Peek();
                        if (C == '"') { Advance(); return true; }
                        if (static_cast<unsigned char>(C) < 0x20) { return Fail("control character in string", Result); }
                        if (C == '\\')
                        {
                                Advance();
                                const char Esc = Peek();
                                switch (Esc)
                                {
                                case '"': Out.push_back('"'); Advance(); break;
                                case '\\': Out.push_back('\\'); Advance(); break;
                                case '/': Out.push_back('/'); Advance(); break;
                                case 'b': Out.push_back('\b'); Advance(); break;
                                case 'f': Out.push_back('\f'); Advance(); break;
                                case 'n': Out.push_back('\n'); Advance(); break;
                                case 'r': Out.push_back('\r'); Advance(); break;
                                case 't': Out.push_back('\t'); Advance(); break;
                                case 'u':
                                {
                                        Advance();
                                        unsigned int Code = 0;
                                        if (!ParseHex4(Code)) { return Fail("invalid \\uXXXX escape", Result); }
                                        // surrogate pair
                                        if (Code >= 0xD800 && Code <= 0xDBFF && Peek() == '\\' && PeekAt(1) == 'u')
                                        {
                                                const size_t SavePos = Pos; const int SaveLine = Line; const int SaveCol = Col;
                                                Advance(); Advance();
                                                unsigned int Low = 0;
                                                if (ParseHex4(Low) && Low >= 0xDC00 && Low <= 0xDFFF)
                                                {
                                                        Code = 0x10000 + ((Code - 0xD800) << 10) + (Low - 0xDC00);
                                                }
                                                else
                                                {
                                                        Pos = SavePos; Line = SaveLine; Col = SaveCol;
                                                }
                                        }
                                        AppendUtf8(Out, Code);
                                        break;
                                }
                                default:
                                        return Fail("invalid escape sequence", Result);
                                }
                                continue;
                        }
                        Out.push_back(C);
                        Advance();
                }
                return Fail("unterminated string", Result);
        }

        bool ParseNumber(double& Out, JsonParseResult& Result)
        {
                const size_t Start = Pos;
                if (Peek() == '-' || Peek() == '+') { Advance(); }
                while (!AtEnd())
                {
                        const char C = Peek();
                        if ((C >= '0' && C <= '9') || C == '.' || C == 'e' || C == 'E' || C == '+' || C == '-') { Advance(); }
                        else { break; }
                }
                if (Pos == Start) { return Fail("expected number", Result); }
                const std::string NumText = Text.substr(Start, Pos - Start);
                char* EndPtr = nullptr;
                const double Value = std::strtod(NumText.c_str(), &EndPtr);
                if (EndPtr == nullptr || *EndPtr != '\0') { return Fail("malformed number '" + NumText + "'", Result); }
                if (std::isnan(Value) || std::isinf(Value)) { return Fail("number out of range", Result); }
                Out = Value;
                return true;
        }

        bool ParseValue(JsonValue& Out, JsonParseResult& Result)
        {
                SkipWhitespace();
                if (AtEnd()) { return Fail("unexpected end of input", Result); }

                const char C = Peek();
                if (C == '{')
                {
                        Advance();
                        Out = JsonValue::MakeObject();
                        SkipWhitespace();
                        if (Peek() == '}') { Advance(); return true; }
                        while (true)
                        {
                                SkipWhitespace();
                                std::string Key;
                                if (!ParseString(Key, Result)) { return false; }
                                SkipWhitespace();
                                if (Peek() != ':') { return Fail("expected ':' after object key", Result); }
                                Advance();
                                JsonValue Member;
                                if (!ParseValue(Member, Result)) { return false; }
                                Out.Set(Key, std::move(Member));
                                SkipWhitespace();
                                if (Peek() == ',') { Advance(); continue; }
                                if (Peek() == '}') { Advance(); return true; }
                                return Fail("expected ',' or '}' in object", Result);
                        }
                }
                if (C == '[')
                {
                        Advance();
                        Out = JsonValue::MakeArray();
                        SkipWhitespace();
                        if (Peek() == ']') { Advance(); return true; }
                        while (true)
                        {
                                JsonValue Item;
                                if (!ParseValue(Item, Result)) { return false; }
                                Out.Append(std::move(Item));
                                SkipWhitespace();
                                if (Peek() == ',') { Advance(); continue; }
                                if (Peek() == ']') { Advance(); return true; }
                                return Fail("expected ',' or ']' in array", Result);
                        }
                }
                if (C == '"')
                {
                        std::string S;
                        if (!ParseString(S, Result)) { return false; }
                        Out = JsonValue(S);
                        return true;
                }
                if (C == 't')
                {
                        if (Text.compare(Pos, 4, "true") == 0) { for (int I = 0; I < 4; ++I) { Advance(); } Out = JsonValue(true); return true; }
                        return Fail("invalid literal", Result);
                }
                if (C == 'f')
                {
                        if (Text.compare(Pos, 5, "false") == 0) { for (int I = 0; I < 5; ++I) { Advance(); } Out = JsonValue(false); return true; }
                        return Fail("invalid literal", Result);
                }
                if (C == 'n')
                {
                        if (Text.compare(Pos, 4, "null") == 0) { for (int I = 0; I < 4; ++I) { Advance(); } Out = JsonValue(); return true; }
                        return Fail("invalid literal", Result);
                }
                double Num = 0.0;
                return ParseNumber(Num, Result) ? (Out = JsonValue(Num), true) : false;
        }
};

} // anonymous namespace

namespace
{

void SerializeTo(const JsonValue& V, std::string& Out, bool bPretty, int Depth)
{
        const std::string Indent = bPretty ? std::string(static_cast<size_t>(Depth) * 2, ' ') : "";
        const std::string IndentInner = bPretty ? std::string(static_cast<size_t>(Depth + 1) * 2, ' ') : "";
        const std::string NewLine = bPretty ? "\n" : "";

        switch (V.GetType())
        {
        case JsonValue::Type::Null:
                Out += "null";
                break;
        case JsonValue::Type::Bool:
                Out += V.AsBool() ? "true" : "false";
                break;
        case JsonValue::Type::Number:
        {
                char Buf[64];
                const double D = V.AsNumber();
                if (std::floor(D) == D && std::fabs(D) < 1.0e15)
                {
                        std::snprintf(Buf, sizeof(Buf), "%lld", static_cast<long long>(D));
                }
                else
                {
                        std::snprintf(Buf, sizeof(Buf), "%.10g", D);
                }
                Out += Buf;
                break;
        }
        case JsonValue::Type::String:
                Out += '"';
                Out += JsonEscape(V.AsString());
                Out += '"';
                break;
        case JsonValue::Type::Array:
        {
                Out += '[';
                const size_t N = V.Size();
                for (size_t I = 0; I < N; ++I)
                {
                        if (I > 0) { Out += ','; if (bPretty) { Out += ' '; } }
                        Out += IndentInner;
                        SerializeTo(*V.At(I), Out, bPretty, Depth + 1);
                }
                if (N > 0 && bPretty) { Out += NewLine + Indent; }
                Out += ']';
                break;
        }
        case JsonValue::Type::Object:
        {
                Out += '{' + NewLine;
                const auto& Obj = V.AsObject();
                size_t I = 0;
                for (const auto& KV : Obj)
                {
                        if (I > 0) { Out += ',' + NewLine; }
                        Out += IndentInner + '"' + JsonEscape(KV.first) + '"' + (bPretty ? ": " : ":");
                        SerializeTo(KV.second, Out, bPretty, Depth + 1);
                        ++I;
                }
                Out += NewLine + Indent + '}';
                break;
        }
        }
}

} // anonymous namespace

JsonParseResult JsonParse(const std::string& Text)
{
        JsonParseResult Result;
        Parser P(Text);
        JsonValue Root;
        if (!P.ParseValue(Root, Result))
        {
                return Result;
        }
        P.SkipWhitespace();
        if (!P.AtEnd())
        {
                P.Fail("trailing content after JSON value", Result);
                return Result;
        }
        Result.Ok = true;
        Result.Value = std::move(Root);
        return Result;
}

std::string JsonSerialize(const JsonValue& Value, bool bPretty)
{
        std::string Out;
        SerializeTo(Value, Out, bPretty, 0);
        return Out;
}

std::string JsonEscape(const std::string& S)
{
        std::string Out;
        Out.reserve(S.size() + 8);
        for (size_t I = 0; I < S.size(); ++I)
        {
                const unsigned char C = static_cast<unsigned char>(S[I]);
                switch (C)
                {
                case '"': Out += "\\\""; break;
                case '\\': Out += "\\\\"; break;
                case '\b': Out += "\\b"; break;
                case '\f': Out += "\\f"; break;
                case '\n': Out += "\\n"; break;
                case '\r': Out += "\\r"; break;
                case '\t': Out += "\\t"; break;
                default:
                        if (C < 0x20)
                        {
                                char Buf[8];
                                std::snprintf(Buf, sizeof(Buf), "\\u%04x", C);
                                Out += Buf;
                        }
                        else
                        {
                                Out.push_back(static_cast<char>(C));
                        }
                }
        }
        return Out;
}

} // namespace tls
