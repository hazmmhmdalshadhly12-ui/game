// THE LAST SIN: The Sin-Eater - M1
// TLSProceduralAudio.cpp - PCM synthesis for the placeholder ambience.

#include "TLSProceduralAudio.h"

#include "Components/AudioComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Sound/SoundWaveProcedural.h"

namespace
{
        // cheap deterministic pseudo-noise (xorshift32)
        uint32 NextNoise(uint32& State)
        {
                State ^= State << 13;
                State ^= State >> 17;
                State ^= State << 5;
                return State;
        }

        void AppendSample(TArray<uint8>& OutPcm, float Sample01)
        {
                // clamp + convert to signed 16-bit little-endian
                if (Sample01 > 1.0f) { Sample01 = 1.0f; }
                if (Sample01 < -1.0f) { Sample01 = -1.0f; }
                const int16 Value = static_cast<int16>(Sample01 * 32767.0f);
                OutPcm.Add(static_cast<uint8>(Value & 0xFF));
                OutPcm.Add(static_cast<uint8>((Value >> 8) & 0xFF));
        }
}

UTLSProceduralAudioComponent::UTLSProceduralAudioComponent()
{
        PrimaryComponentTick.bCanEverTick = true;
        PrimaryComponentTick.TickInterval = 0.1f;
}

void UTLSProceduralAudioComponent::BeginPlay()
{
        Super::BeginPlay();
        EnsureLayers();
}

void UTLSProceduralAudioComponent::EnsureLayers()
{
        if (!WindWave)
        {
                WindWave = NewObject<USoundWaveProcedural>(GetOwner());
                if (WindWave)
                {
                        WindWave->SetSampleRate(SampleRate);
                        WindWave->NumChannels = 1;
                        WindWave->bLooping = false;
                        WindWave->Duration = 3600.0f;   // fed continuously in Tick
                }
                WindSource = UGameplayStatics::CreateAudioComponent(GetOwner() ? GetOwner() : this, WindWave, FVector::ZeroVector, false, false);
                if (WindSource) { WindSource->SetVolumeMultiplier(0.0f); WindSource->Play(); }
        }
        if (!RainWave)
        {
                RainWave = NewObject<USoundWaveProcedural>(GetOwner());
                if (RainWave)
                {
                        RainWave->SetSampleRate(SampleRate);
                        RainWave->NumChannels = 1;
                        RainWave->bLooping = false;
                        RainWave->Duration = 3600.0f;
                }
                RainSource = UGameplayStatics::CreateAudioComponent(GetOwner() ? GetOwner() : this, RainWave, FVector::ZeroVector, false, false);
                if (RainSource) { RainSource->SetVolumeMultiplier(0.0f); RainSource->Play(); }
        }
}

void UTLSProceduralAudioComponent::SetWeatherBlend(float RainAmount)
{
        RainBlend = FMath::Clamp(RainAmount, 0.0f, 1.0f);
}

void UTLSProceduralAudioComponent::SynthesizeNoise(TArray<uint8>& OutPcm, int32 NumSamples, float Highpass01, float Amplitude, int32 Seed)
{
        uint32 State = static_cast<uint32>(Seed) | 1u;
        float Previous = 0.0f;
        for (int32 I = 0; I < NumSamples; ++I)
        {
                const float White = (static_cast<float>(NextNoise(State) & 0xFFFF) / 32768.0f) - 1.0f;
                // one-pole highpass: emphasize hiss for rain, leave rumble for wind
                const float Filtered = White - (Highpass01 * Previous);
                Previous = White;
                AppendSample(OutPcm, Filtered * Amplitude);
        }
}

void UTLSProceduralAudioComponent::SynthesizeBell(TArray<uint8>& OutPcm)
{
        // three decaying partials, ~1.4 s, C#3-ish strike
        const float PartialHz[3] = { 138.6f, 277.2f, 415.3f };
        const float PartialAmp[3] = { 0.55f, 0.3f, 0.12f };
        const float Decay[3] = { 1.1f, 0.8f, 0.5f };
        const int32 NumSamples = static_cast<int32>(SampleRate * 1.4f);
        for (int32 I = 0; I < NumSamples; ++I)
        {
                const float T = static_cast<float>(I) / SampleRate;
                float Sample = 0.0f;
                for (int32 P = 0; P < 3; ++P)
                {
                        Sample += PartialAmp[P] * FMath::Exp(-T * Decay[P]) * FMath::Sin(2.0f * PI * PartialHz[P] * T);
                }
                AppendSample(OutPcm, Sample * 0.8f);
        }
}

void UTLSProceduralAudioComponent::QueuePcm(USoundWaveProcedural* Wave, const TArray<uint8>& Pcm)
{
        if (Wave && Pcm.Num() > 0)
        {
                Wave->QueueAudioData(Pcm.GetData(), Pcm.Num());
        }
}

void UTLSProceduralAudioComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTick)
{
        Super::TickComponent(DeltaTime, TickType, ThisTick);
        if (!WindWave || !RainWave) { EnsureLayers(); }
        if (!WindWave || !RainWave) { return; }

        // feed ~0.5 s of PCM per layer per tick (kept small on purpose)
        SecondsSinceWindQueue += DeltaTime;
        if (SecondsSinceWindQueue >= 0.4f)
        {
                const int32 NumSamples = static_cast<int32>(SampleRate * 0.6f);
                TArray<uint8> Pcm;
                Pcm.Reserve(NumSamples * 2);
                // wind breathes: slow amplitude LFO
                WindPhase += 0.6f * SecondsSinceWindQueue;
                const float Breath = 0.55f + 0.45f * FMath::Sin(WindPhase);
                SynthesizeNoise(Pcm, NumSamples, 0.15f, 0.16f * Breath, NoiseSeedWind += 101);
                QueuePcm(WindWave, Pcm);
                SecondsSinceWindQueue = 0.0f;
        }
        SecondsSinceRainQueue += DeltaTime;
        if (RainBlend > 0.01f && SecondsSinceRainQueue >= 0.4f)
        {
                const int32 NumSamples = static_cast<int32>(SampleRate * 0.6f);
                TArray<uint8> Pcm;
                Pcm.Reserve(NumSamples * 2);
                SynthesizeNoise(Pcm, NumSamples, 0.85f, 0.14f, NoiseSeedRain += 103);
                QueuePcm(RainWave, Pcm);
                SecondsSinceRainQueue = 0.0f;
        }

        if (WindSource) { WindSource->SetVolumeMultiplier(0.5f * (1.0f - 0.35f * RainBlend)); }
        if (RainSource) { RainSource->SetVolumeMultiplier(0.7f * RainBlend); }
}

void UTLSProceduralAudioComponent::PlayBell()
{
        if (!GetWorld()) { return; }

        USoundWaveProcedural* BellWave = NewObject<USoundWaveProcedural>(GetOwner() ? GetOwner() : this);
        if (!BellWave) { return; }
        BellWave->SetSampleRate(SampleRate);
        BellWave->NumChannels = 1;
        BellWave->bLooping = false;

        TArray<uint8> Pcm;
        SynthesizeBell(Pcm);
        QueuePcm(BellWave, Pcm);

        UAudioComponent* BellSource = UGameplayStatics::CreateAudioComponent(GetOwner(), BellWave, FVector::ZeroVector, false, false);
        if (BellSource)
        {
                BellSource->SetVolumeMultiplier(0.6f);
                BellSource->Play();
        }
}
