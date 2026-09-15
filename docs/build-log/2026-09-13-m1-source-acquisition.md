# 2026-09-13: Milestone 1 source acquisition

## Work recorded

Downloaded the initial GeoNames and OurAirports inputs for local Milestone 1
inspection. The files are intentionally stored in the ignored repository-local
directory `data/source-inputs/`; they are not part of the Git history or a
published knowledge snapshot.

## Inputs and verification

| Source | Files | Verification |
| --- | --- | --- |
| GeoNames export dump | `allCountries.zip`, `alternateNamesV2.zip`, `countryInfo.txt`, `admin1CodesASCII.txt`, `admin2Codes.txt`, `hierarchy.zip`, `timeZones.txt` | SHA-256 calculated for every file; `unzip -t` passed for the three ZIP archives. |
| OurAirports data download | `airports.csv`, `countries.csv`, `regions.csv` | SHA-256 calculated for every file. |

The local bundle occupies approximately 642 MB. The acquisition agent recorded
the following source receipts. A durable raw-artifact retention policy remains
owner-deferred; this ignored local staging area is not that policy.

| File | URL | SHA-256 |
| --- | --- | --- |
| `allCountries.zip` | `https://download.geonames.org/export/dump/allCountries.zip` | `0a90c49c9b4f0c76965469df22d507eb82b80da8e1cef8ec058be2bbdab2c287` |
| `alternateNamesV2.zip` | `https://download.geonames.org/export/dump/alternateNamesV2.zip` | `6ebd03faf9f99ec405ec8263bc88ac51aa0c6220ca221f92defddae38082089b` |
| `countryInfo.txt` | `https://download.geonames.org/export/dump/countryInfo.txt` | `93bafc525813f22e4711ff9ed6d626343094ce48c26388dc7c49189b3d7d5512` |
| `admin1CodesASCII.txt` | `https://download.geonames.org/export/dump/admin1CodesASCII.txt` | `590651498043f674accda2b7f46d21286cda0e290b02f8561c5005eee9a5448c` |
| `admin2Codes.txt` | `https://download.geonames.org/export/dump/admin2Codes.txt` | `e5a155147287d642a0fd9f9ee9a809e9d7f632f6002defd82db91d9f41c20553` |
| `hierarchy.zip` | `https://download.geonames.org/export/dump/hierarchy.zip` | `73b1d988926d571120db99d10e0f4153f3ab767d9200caf9dedb0943c1f69de2` |
| `timeZones.txt` | `https://download.geonames.org/export/dump/timeZones.txt` | `ea6f8bdcc259c21c562e8f7e7e0b0457cb89403bed60c76aac49ccee9a9ed18c` |
| `airports.csv` | `https://davidmegginson.github.io/ourairports-data/airports.csv` | `8bb6f48835fbedc41e6294c570980c16c5d3014e3a529927f6aa9dbdd1c38327` |
| `countries.csv` | `https://davidmegginson.github.io/ourairports-data/countries.csv` | `2a9dbee691125b0cdb8ceb5fe227c48c903f99c488963b8e53e2ab366521c639` |
| `regions.csv` | `https://davidmegginson.github.io/ourairports-data/regions.csv` | `63bc8012a4e5449867b81ab510a722f5f98cedd8ea56fe09e113c9d630cd21b4` |

## Local airport-source preparation

With owner approval, the ignored local `data/source-inputs/airports.csv` was
overwritten with a CSV that retains its original header and only rows whose
OurAirports `type` is `large_airport` or `medium_airport`. The original complete
OurAirports file is not retained locally.

- Retained rows: 5,280 (1,174 large; 4,106 medium).
- Retained rows with an IATA code: 4,569.
- Filtered file SHA-256:
  `b57ceba1a5048e93af354cf766bd67bffd723878e81173df869136d2b68d7557`.

The `airports.csv` receipt in the preceding table is the checksum of the full
download before this owner-approved local filtering, not the checksum of the
current ignored file. The future importer must treat the filtering rule and
current checksum as its actual local input receipt.

## Files changed

- `.gitignore` now excludes `data/source-inputs/`.

## Verification

- Recalculated all ten SHA-256 values after moving the files into the ignored
  repository-local directory; they matched the download receipts.
- `git status --ignored` shows `data/source-inputs/` as ignored.
- No production code, snapshot, fixture, dependency, or provider behavior
  changed.
