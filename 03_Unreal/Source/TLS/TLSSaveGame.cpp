// THE LAST SIN: The Sin-Eater - M1
// TLSSaveGame.cpp - the slot wrapper (slot name constant + helpers).

#include "TLSSaveGame.h"

#include "Kismet/GameplayStatics.h"
#include "Misc/DateTime.h"

namespace TLSSave
{
        const TCHAR* SlotName = TEXT("TLSSliceSlot");

        UTLSSaveGame* CreateSavePayload(const FString& Payload, int32 Day)
        {
                UTLSSaveGame* Save = Cast<UTLSSaveGame>(UGameplayStatics::CreateSaveGameObject(UTLSSaveGame::StaticClass()));
                if (Save)
                {
                        Save->Payload = Payload;
                        Save->Day = Day;
                        Save->Timestamp = FDateTime::UtcNow().ToUnixTimestamp();
                }
                return Save;
        }

        bool WriteSlot(const FString& Payload, int32 Day)
        {
                UTLSSaveGame* Save = CreateSavePayload(Payload, Day);
                return Save && UGameplayStatics::SaveGameToSlot(Save, SlotName, 0);
        }

        bool ReadSlot(FString& OutPayload, int32& OutDay)
        {
                UTLSSaveGame* Save = Cast<UTLSSaveGame>(UGameplayStatics::LoadGameFromSlot(SlotName, 0));
                if (!Save) { return false; }
                OutPayload = Save->Payload;
                OutDay = Save->Day;
                return true;
        }
}
