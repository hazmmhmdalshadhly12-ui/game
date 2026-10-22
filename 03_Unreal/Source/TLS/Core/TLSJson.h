// THE LAST SIN: The Sin-Eater - M1
// TLSJson: minimal, dependency-free JSON parser/serializer for the game-logic
// core. Pure C++17 (no engine includes, no exceptions, no filesystem) so the
// exact same file compiles standalone (g++ test harness) and inside the UE
// module (MSVC). Deterministic output (objects keep sorted keys) so save-game
// round-trips are byte-stable and testable.

#pragma once

#include <map>
#include <string>
#include <vector>

namespace tls
{

class JsonValue
{
public:
        enum class Type
        {
                Null,
                Bool,
                Number,
                String,
                Array,
                Object
        };

        JsonValue() : TypeV(Type::Null), BoolV(false), NumberV(0.0) {}
        JsonValue(bool B) : TypeV(Type::Bool), BoolV(B), NumberV(0.0) {}
        JsonValue(double N) : TypeV(Type::Number), BoolV(false), NumberV(N) {}
        JsonValue(int N) : TypeV(Type::Number), BoolV(false), NumberV(static_cast<double>(N)) {}
        JsonValue(const char* S) : TypeV(Type::String), BoolV(false), NumberV(0.0), StringV(S ? S : "") {}
        JsonValue(const std::string& S) : TypeV(Type::String), BoolV(false), NumberV(0.0), StringV(S) {}

        // factories for empty containers (Set/Append also switch the type)
        static JsonValue MakeObject() { JsonValue V; V.TypeV = Type::Object; return V; }
        static JsonValue MakeArray() { JsonValue V; V.TypeV = Type::Array; return V; }

        Type GetType() const { return TypeV; }
        bool IsNull() const { return TypeV == Type::Null; }
        bool IsBool() const { return TypeV == Type::Bool; }
        bool IsNumber() const { return TypeV == Type::Number; }
        bool IsString() const { return TypeV == Type::String; }
        bool IsArray() const { return TypeV == Type::Array; }
        bool IsObject() const { return TypeV == Type::Object; }

        bool AsBool(bool Default = false) const { return IsBool() ? BoolV : Default; }
        double AsNumber(double Default = 0.0) const { return IsNumber() ? NumberV : Default; }
        int AsInt(int Default = 0) const { return IsNumber() ? static_cast<int>(NumberV) : Default; }
        const std::string& AsString() const { static const std::string Empty; return IsString() ? StringV : Empty; }

        // --- array access ---
        size_t Size() const { return ArrayV.size(); }
        const JsonValue* At(size_t Index) const { return Index < ArrayV.size() ? &ArrayV[Index] : nullptr; }
        JsonValue& Append(JsonValue V) { TypeV = Type::Array; ArrayV.push_back(std::move(V)); return ArrayV.back(); }

        // --- object access ---
        const JsonValue* Find(const std::string& Key) const
        {
                if (TypeV != Type::Object) { return nullptr; }
                auto It = ObjectV.find(Key);
                return It == ObjectV.end() ? nullptr : &It->second;
        }
        bool Has(const std::string& Key) const { return Find(Key) != nullptr; }
        JsonValue& Set(const std::string& Key, JsonValue V)
        {
                TypeV = Type::Object;
                ObjectV[Key] = std::move(V);
                return ObjectV[Key];
        }

        // typed object-member helpers (return defaults when missing/mistyped)
        bool GetBool(const std::string& Key, bool Default) const
        {
                const JsonValue* V = Find(Key);
                return (V && V->IsBool()) ? V->BoolV : Default;
        }
        double GetNumber(const std::string& Key, double Default) const
        {
                const JsonValue* V = Find(Key);
                return (V && V->IsNumber()) ? V->NumberV : Default;
        }
        int GetInt(const std::string& Key, int Default) const
        {
                const JsonValue* V = Find(Key);
                return (V && V->IsNumber()) ? static_cast<int>(V->NumberV) : Default;
        }
        std::string GetString(const std::string& Key, const std::string& Default) const
        {
                const JsonValue* V = Find(Key);
                return (V && V->IsString()) ? V->StringV : Default;
        }
        std::vector<std::string> GetStringList(const std::string& Key) const
        {
                std::vector<std::string> Out;
                if (const JsonValue* V = Find(Key))
                {
                        for (size_t I = 0; I < V->Size(); ++I)
                        {
                                if (const JsonValue* Item = V->At(I)) { if (Item->IsString()) { Out.push_back(Item->AsString()); } }
                        }
                }
                return Out;
        }

        const std::map<std::string, JsonValue>& AsObject() const { return ObjectV; }
        const std::vector<JsonValue>& AsArray() const { return ArrayV; }

private:
        Type TypeV;
        bool BoolV;
        double NumberV;
        std::string StringV;
        std::vector<JsonValue> ArrayV;
        std::map<std::string, JsonValue> ObjectV;
};

struct JsonParseResult
{
        bool Ok = false;
        JsonValue Value;
        std::string Error;
        int Line = 0;
        int Column = 0;
};

// Parses strict JSON (UTF-8). \uXXXX escapes are decoded to UTF-8.
JsonParseResult JsonParse(const std::string& Text);

// Serializes with 2-space indentation when bPretty, otherwise compact.
// Object keys are emitted in sorted (map) order - deterministic output.
std::string JsonSerialize(const JsonValue& Value, bool bPretty = true);

// Utilities used by the core systems.
std::string JsonEscape(const std::string& S);

} // namespace tls
