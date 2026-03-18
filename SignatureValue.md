# Star Citizen Mining Signature Value Analysis

**Extraction Date:** 2026-03-18 (SC Patch 4.7)
**Source:** Game2.xml via unp4k-suite v3.13.66 from Data.p4k
**Extraction Tool:** `extract_all_signatures.py` (sc_data_extractor project)
**Author:** Mallachi

> **SC 4.7 Breaking Change:** The old I/C/S/P/M/Q/E asteroid type system is completely removed.
> The new system uses per-mineral signatures — each mineral has a unique signature value that
> directly identifies it, regardless of whether it appears in an asteroid or a surface rock.

---

## Table of Contents

1. [Summary of Findings](#summary-of-findings)
2. [SC 4.7 Changes vs 4.6](#sc-47-changes-vs-46)
3. [Ship Mining — Per-Mineral Signatures](#ship-mining--per-mineral-signatures)
4. [Ground Deposits](#ground-deposits)
5. [Salvage](#salvage)
6. [Undetectable Entities](#undetectable-entities)
7. [Signature Collisions](#signature-collisions)
8. [Extraction Methodology](#extraction-methodology)
9. [DCB Parsing Technical Details](#dcb-parsing-technical-details)

---

## Summary of Findings

### Quick Reference Table

| Category | Signature(s) | Notes |
|---|---|---|
| **Legendary minerals** | 3170, 3185, 3200 | Quantainium, Stileron (Sileron ore), Savrilium |
| **Epic minerals** | 3370, 3385, 3400 | Ouratite, Riccite, Lindinium |
| **Rare minerals** | 3540, 3555, 3570, 3585, 3600 | Beryl, Taranite, Borase, Gold, Bexalite |
| **Uncommon minerals** | 3825, 3840, 3855, 3870, 3885, 3900 | Laranite, Aslarite, Titanium, Tungsten, Agricium, Torite |
| **Common minerals** | 4180–4300 (15-step increments) | Hephaestanite, Tin, Quartz, Corundum, Copper, Silicon, Iron, Aluminum, Ice |
| **FPS Ground Deposit (small)** | 3000 | Confirmed SC 4.7 DCB |
| **ROC/GV Ground Deposit (large)** | 4000 | Confirmed SC 4.7 DCB (was incorrectly 3000 in pre-4.7 DB) |
| **Salvage Panels / Active Scrap** | 2000 | Per panel |
| **Small Wreck Debris** | 1700 | Avenger-class hull pieces |
| **Medium Wreck Debris** | 1850 | Ares Inferno-class hull pieces |
| **Large Wreck Debris** | 2400 | C2 Hercules-class hull pieces |
| **Capital Wreck Debris** | 3000 | 890 Jump-class — COLLISION with FPS ground deposit |
| **Undetectable** | 0 | Vlk Pearls, Vlk Irradiated Pearls, Flowstone |

---

## SC 4.7 Changes vs 4.6

| Category | SC 4.6 | SC 4.7 |
|---|---|---|
| Asteroid type system | I/C/S/P/M/Q/E types with shared signatures | **REMOVED** |
| Ship mining identification | Type-based (e.g. C-type = 4700, E-type = 4900) | Per-mineral unique signature |
| Rock composition | Mixed minerals per asteroid type | 100% single mineral per rock — signature IS the mineral |
| Surface deposits | 4000 (all types, CIG bug) | Still 4000, but now mineral-specific asteroids exist |
| FPS ground deposits | 3000 | 3000 (unchanged) |
| ROC/GV ground deposits | Listed as 3000 in old DB (incorrect) | **4000** (confirmed, resolved discrepancy) |
| Salvage panels | 2000 | 2000 (unchanged) |
| Salvage debris | Not in game | **NEW** — 1700 / 1850 / 2400 / 3000 by hull size |
| Signature 3000 collision | FPS ground deposit only | FPS ground deposit + Capital Wreck Debris (890 Jump) |

---

## Ship Mining — Per-Mineral Signatures

Ship mining only (Prospector, MOLE). The signature identifies the **dominant mineral** (40–80% composition). Rocks also contain secondary minerals (5–20%) — they are not pure. Applies to both asteroids and planetary surface rocks.

**Source:** `mining_data-4.7.0-ptu.11450623.json` (Miner's Refuge). Note: PTU build — compositions may differ slightly from live 4.7.

### Legendary Tier (3170–3200)

Highest value minerals. Extremely rare spawns.

| Mineral | Signature | Secondary minerals |
|---|---|---|
| Quantainium | 3170 | + Beryl (10–20%) |
| Stileron *(Sileron ore)* | 3185 | + Taranite (10–20%) |
| Savrilium | 3200 | + Gold (10–20%) |

### Epic Tier (3370–3400)

| Mineral | Signature | Secondary minerals |
|---|---|---|
| Ouratite | 3370 | + Agricium (10–20%) |
| Riccite | 3385 | + Laranite (10–20%) |
| Lindinium | 3400 | + Tungsten (10–20%) |

### Rare Tier (3540–3600)

| Mineral | Signature | Secondary minerals |
|---|---|---|
| Beryl | 3540 | none (50–100% pure) |
| Taranite | 3555 | none (50–100% pure) |
| Borase | 3570 | + Gold (5–10%) + Bexalite (5–10%) |
| Gold | 3585 | + Borase (5–10%) + Bexalite (5–10%) |
| Bexalite | 3600 | + Gold (5–10%) + Borase (5–10%) |

### Uncommon Tier (3825–3900)

| Mineral | Signature | Secondary minerals |
|---|---|---|
| Laranite | 3825 | + Tungsten (10–20%) |
| Aslarite | 3840 | + Titanium (5–10%) + Agricium (5–10%) |
| Titanium | 3855 | + Aslarite (5–10%) + Agricium (5–10%) |
| Tungsten | 3870 | + Laranite (10–20%) |
| Agricium | 3885 | + Titanium (5–10%) + Aslarite (5–10%) |
| Torite | 3900 | none (50–100% pure) |

### Common Tier (4180–4300)

| Mineral | Signature | Secondary minerals |
|---|---|---|
| Hephaestanite | 4180 | + Quartz (5–10%) + Silicon (5–10%) |
| Tin | 4195 | + Copper (10–20%) |
| Quartz | 4210 | + Hephaestanite (5–10%) + Silicon (5–10%) |
| Corundum | 4225 | + Aluminium (10–20%) |
| Copper | 4240 | + Tin (10–20%) |
| Silicon | 4255 | + Hephaestanite (5–10%) + Quartz (5–10%) |
| Iron | 4270 | none (50–100% pure) |
| Aluminum | 4285 | + Corundum (10–20%) |
| Ice | 4300 | none (50–100% pure) |

---

## Ground Deposits

ROC or FPS mining. 100% single mineral per cluster. The signature identifies **size** only — not which mineral.

### Small Deposits (FPS/Hand Mining) — Signature: 3000

| Entity Pattern | Signature | Method |
|---|---|---|
| MineableRock_FPS_* | 3000 | FPS/Hand tool (can be vehicle-mined with skill) |

**Possible minerals:** Hadanite, Dolivine, Aphorite, Beradom, Glacosite, Feynmaline, Jaclium, Sadaryx, Janalite, Saldynium, Carinite

**Cluster rules:**
- Each cluster spawns ONE mineral type at 100% purity
- A mineral spawns as either small OR large deposits, never both in same cluster

### Large Deposits (ROC/Vehicle Mining) — Signature: 4000

| Entity Pattern | Signature | Method |
|---|---|---|
| MineableRock_GroundVehicle_* | 4000 | ROC/Ground vehicle (can be FPS-mined collaboratively) |

**Possible minerals:** Same list as small deposits above.

**Note:** Signature 4000 collides with old surface deposit entities. Context determines type — on a planet surface at ground level = ground deposit.

### Resolved Discrepancy

The pre-4.7 database listed ROC/GV rocks as signature 3000. This was incorrect. The SC 4.7 DCB confirms **4000**. The C-1 bug (wrong value in DB) is fixed.

---

## Salvage

### Salvage Panels / Active Scrap — Signature: 2000 per panel

Standard hull scraping panels. Total signature = 2000 × panel count.

**Formula:** `panel_count = total_signature ÷ 2000`

Covers: FPS salvage panels, SalvageScrap entities, SalvageableRepairable ship parts, generic metal pieces.

### Wreck Debris — SC 4.7 New

Complete wreck hull pieces with size-based signatures. Added in SC 4.7 salvage gameplay update.

| Size Class | Signature | Example Ship | Method |
|---|---|---|---|
| Small | 1700 | Avenger Titan-class | Tractor beam / collect |
| Medium | 1850 | Ares Inferno-class | Tractor beam / collect |
| Large | 2400 | C2 Hercules-class | Tractor beam / collect |
| Capital | 3000 | 890 Jump-class | Tractor beam / collect |

**Capital debris collision:** Signature 3000 is shared between capital wreck debris and FPS small ground deposits. Cannot be resolved by scanner alone — context determines type (space = likely debris, planetary surface = likely ground deposit).

---

## Undetectable Entities

These entities have signature 0 and will never appear on scanner.

| Entity | Category |
|---|---|
| Vlk Pearls | Ground FPS |
| Vlk Irradiated Pearls | Ground FPS |
| Flowstone | Ground FPS |

---

## Signature Collisions

Signatures that map to more than one entity type. Cannot be resolved by value alone.

| Signature | Colliding Types | Resolution |
|---|---|---|
| **3000** | FPS Small Ground Deposit + Capital Wreck Debris (890 Jump) | Context: space vs planet surface |
| **4000** | ROC/GV Large Ground Deposit + old generic surface entity bases | Context: ground level vs surface rock |

---

## Extraction Methodology

### Data Source

Mining signature values are compiled into `Game2.dcb` (DataCore Binary), a ~285 MB binary file inside Star Citizen's `Data.p4k` archive (142 GB). They are **not** present in any loose XML or JSON files within the p4k.

For SC 4.7, the extraction was performed by converting `Game2.dcb` to `Game2.xml` via unp4k-suite v3.13.66, then parsing the XML for signature-related struct values.

### Entity-to-Signature Chain

Signature values are accessed through a 4-level component pointer chain in the DCB:

```
EntityClassDefinition (size=66 bytes)
  -> Components (StrongPointer ComplexArray @ offset 58, via strong pool)
    -> SSCSignatureSystemParams (size=121 bytes)
      -> radarProperties (inline StrongPointer @ byte 4)
        -> SSCRadarContactProperites (size=61 bytes)
          -> baseSignatureParams (inline StrongPointer @ byte 20)
            -> SSCSignatureSystemBaseSignatureParams (size=24 bytes)
              -> signatures (SimpleArray of Single @ byte 0)
                -> Single value pool [index 4 = cross section]
```

### Critical Technical Note

`SSCSignatureSystemBaseSignatureParams` (BSP) instances have **zero entries** in the DCB strong pointer pool. They are accessed exclusively through **inline StrongPointers** embedded in the data section of parent structs. This is why initial extraction attempts that scanned the strong pool found nothing.

---

## DCB Parsing Technical Details

### Game2.dcb Format

- **Location:** `Data/Game2.dcb` inside `Data.p4k`
- **Compression:** ZStandard (compress_type 100)
- **Decompressed size:** ~285 MB
- **Header:** 120 bytes (30 × uint32)

### Value Pool File Order

The value pools in the DCB file are laid out in a **different order** from the header count fields:

```
Header order: Bool, Int8, Int16, Int32, Int64, UInt8, UInt16, UInt32, UInt64, Single, ...
File order:   Int8, Int16, Int32, Int64, UInt8, UInt16, UInt32, UInt64, Bool, Single, ...
```

Boolean is stored **after** UInt64 in the file, not before Int8 as the header ordering suggests.

### DataType Enum

```
Boolean=0x0001, SByte=0x0002, Int16=0x0003, Int32=0x0004, Int64=0x0005
Byte=0x0006,    UInt16=0x0007, UInt32=0x0008, UInt64=0x0009
String=0x000A,  Single=0x000B, Double=0x000C, Locale=0x000D
Guid=0x000E,    EnumChoice=0x000F
Class=0x0010,   StrongPointer=0x0110, WeakPointer=0x0210, Reference=0x0310
```

### Signature Array Format

Each entity's signature is stored as an **8-element float32 array**. The mining cross-section value is at **index 4**.

```
Index:  [  0,    1,    2,    3,      4,       5,  6,  7  ]
         EM?   IR?   CS?  Audio?  CrossSection  ?   ?   ?
```

| Category | Ch4 (CrossSection) | Notes |
|---|---|---|
| Ship mining rocks | mineral signature | unique per mineral in SC 4.7 |
| Ground deposit FPS small | 3000 | all minerals share this |
| Ground deposit ROC large | 4000 | all minerals share this |
| Salvage panels | 2000 | per panel |
| Wreck debris | 1700 / 1850 / 2400 / 3000 | per hull size class |
| Harvestable plants | 2000 | channel 4 and 5 both set |
| Undetectable | 0 | Vlk Pearls, Flowstone |

### Extraction Scripts

All scripts in `C:\Users\larse\PycharmProjects\AREA52\sc_data_extractor\`:

| Script | Purpose |
|---|---|
| `extract_all_signatures.py` | Production extraction — follows full chain, outputs JSON |
| `extract_47_mining_signatures.py` | SC 4.7-specific extraction from Game2.xml |
| `investigate_47.py` | Phase 1–4 investigation: file recon, CryXmlB decode, DCB structs, location records |
| `parse_dcb_v2.py` | General DCB parser with struct/property/record inspection |

---

*Document updated: 2026-03-18*
*Source: Game2.xml (unp4k-suite v3.13.66) from SC 4.7 Data.p4k*
*Author: Mallachi*
