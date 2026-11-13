# Vendor roster coverage

Generated from [roster.yaml](roster.yaml) by `corpus/roster.py`; do not edit by hand. Status on 2026-11-14.

A model is **mapped** when a contract generated from a checksum-pinned public vendor document exists under [devices/](../devices/). Mapped contracts are reviewed, read-only subsets (`verification: documented`), not complete register maps. **needs-check** and **blocked** models have no contract; the notes give the reason, and [work items](../docs/findings/corpus-work-items.md) say what would unblock them.

| Class | Vendors | Models | Mapped | Needs check | Blocked | Unique layouts | Points |
|---|---|---|---|---|---|---|---|
| 1. Electrical energy submeters | 5 | 15 | 9 | 3 | 3 | 5 | 141 |
| 2. Multifunction power and power-quality meters | 5 | 15 | 6 | 4 | 5 | 3 | 108 |
| 3. Grid-tied PV inverters | 5 | 15 | 6 | 3 | 6 | 2 | 111 |
| 4. Battery energy storage interfaces | 5 | 15 | 8 | 4 | 3 | 3 | 134 |
| 5. Transformer monitoring and tap-changer controllers | 5 | 15 | 9 | 3 | 3 | 8 | 126 |
| 6. Protection relays | 5 | 15 | 12 | 0 | 3 | 8 | 156 |
| 7. Remote I/O | 5 | 15 | 11 | 4 | 0 | 11 | 182 |
| 8. Motor variable-frequency drives | 5 | 15 | 7 | 5 | 3 | 6 | 86 |
| 9. Generator-set controllers | 5 | 15 | 11 | 4 | 0 | 6 | 172 |
| 10. PV irradiance and reference sensors | 5 | 15 | 13 | 2 | 0 | 8 | 151 |
| **Total** | 50 | 150 | 92 | 32 | 26 | 60 | 1367 |

## 1. Electrical energy submeters

| Vendor | Model | Status | Contract | Points | Notes |
|---|---|---|---|---|---|
| ABB | B21 | mapped | [abb/b21/telemetry.omb.yaml](../devices/abb/b21/telemetry.omb.yaml) | 16 | Single-phase: only total and L1 quantities selected. |
| ABB | B23 | mapped | [abb/b23/telemetry.omb.yaml](../devices/abb/b23/telemetry.omb.yaml) | 20 | Same selection as B21 plus L2/L3 voltage and current. |
| ABB | B24 | mapped | [abb/b24/telemetry.omb.yaml](../devices/abb/b24/telemetry.omb.yaml) | 20 | Identical points to B23 (one manual, one map). |
| Carlo Gavazzi | EM511 | mapped | [carlo-gavazzi/em511/telemetry.omb.yaml](../devices/carlo-gavazzi/em511/telemetry.omb.yaml) | 15 | Table 4.1-1 rows. Overflow sentinels 0x7FFF/0x7FFFFFFF (p.11) on instantaneous values. |
| Carlo Gavazzi | EM530 | mapped | [carlo-gavazzi/em530/telemetry.omb.yaml](../devices/carlo-gavazzi/em530/telemetry.omb.yaml) | 19 | Table 4.2 (grouped by phase), which gives a weight per row. |
| Carlo Gavazzi | EM540 | mapped | [carlo-gavazzi/em540/telemetry.omb.yaml](../devices/carlo-gavazzi/em540/telemetry.omb.yaml) | 19 | Same points as EM530; identification enum limited to EM540 part numbers. |
| Eastron | SDM120 | mapped | [eastron/sdm120-modbus/telemetry.omb.yaml](../devices/eastron/sdm120-modbus/telemetry.omb.yaml) | 5 | Already mapped in the pilot; |
| Eastron | SDM230 | mapped | [eastron/sdm230-modbus/telemetry.omb.yaml](../devices/eastron/sdm230-modbus/telemetry.omb.yaml) | 11 | Same input addresses as SDM120 for the common quantities. |
| Eastron | SDM630 | mapped | [eastron/sdm630-modbus/telemetry.omb.yaml](../devices/eastron/sdm630-modbus/telemetry.omb.yaml) | 16 | Wiring-system validity columns (3P4W/3P3W/1P2W, X reads zero) copied into each point description. |
| Schneider Electric | iEM3155 | needs-check |  |  | Every core quantity (current, voltage, power, frequency, energy) is Float32 or Int64 and the document never states the register order; |
| Schneider Electric | iEM3255 | needs-check |  |  | Every core quantity (current, voltage, power, frequency, energy) is Float32 or Int64 and the document never states the register order; |
| Schneider Electric | iEM3355 | needs-check |  |  | Every core quantity (current, voltage, power, frequency, energy) is Float32 or Int64 and the document never states the register order; |
| Socomec | COUNTIS E23 | blocked |  |  | Source returns HTTP 403 (Cloudflare challenge) from this machine; |
| Socomec | COUNTIS E24 | blocked |  |  | Source returns HTTP 403 (Cloudflare challenge) from this machine; |
| Socomec | COUNTIS E43 | blocked |  |  | Source returns HTTP 403 (Cloudflare challenge) from this machine; |

## 2. Multifunction power and power-quality meters

| Vendor | Model | Status | Contract | Points | Notes |
|---|---|---|---|---|---|
| ABB | M4M 20 Modbus | mapped | [abb/m4m-20-modbus/telemetry.omb.yaml](../devices/abb/m4m-20-modbus/telemetry.omb.yaml) | 19 | Product type ID 1. Energies (import, export, net, reactive import; |
| ABB | M4M 30 Modbus | mapped | [abb/m4m-30-modbus/telemetry.omb.yaml](../devices/abb/m4m-30-modbus/telemetry.omb.yaml) | 19 | Product type ID 7. Same rows and point list as the M4M 20 Modbus. |
| ABB | M4M 2X Modbus | mapped | [abb/m4m-2x-modbus/telemetry.omb.yaml](../devices/abb/m4m-2x-modbus/telemetry.omb.yaml) | 19 | Mapped as product type ID 15, which the Details sheet names "M4M 2X RTU"; |
| Eaton | Power Xpert Meter 4000 | blocked |  |  | The source could not be fetched (c02-eaton-access). |
| Eaton | Power Xpert Meter 6000 | blocked |  |  | The source could not be fetched (c02-eaton-access). |
| Eaton | Power Xpert Meter 8000 | blocked |  |  | The source could not be fetched (c02-eaton-access). |
| Janitza electronics | UMG 96RM | mapped | [janitza/umg-96rm/telemetry.omb.yaml](../devices/janitza/umg-96rm/telemetry.omb.yaml) | 17 | From the "Häufig benötigte Messwerte" block (19000 to 19116): phase and line voltage, phase currents, total P/Q/S, frequency, THD of U L1-N and I L1. |
| Janitza electronics | UMG 96RM-E | mapped | [janitza/umg-96rm-e/telemetry.omb.yaml](../devices/janitza/umg-96rm-e/telemetry.omb.yaml) | 17 | Same rows and addresses as the UMG 96RM, read from the English UMG 96RM-E list. |
| Janitza electronics | UMG 96RM-PN | mapped | [janitza/umg-96rm-pn/telemetry.omb.yaml](../devices/janitza/umg-96rm-pn/telemetry.omb.yaml) | 17 | The base-device list applies to the PN extension. |
| Schneider Electric | PM5110 | blocked |  |  | The only register list found is the legacy .xls (c02-schneider-xls-reader). |
| Schneider Electric | PM5330 | blocked |  |  | Same as PM5110. |
| Schneider Electric | PM5560 | needs-check |  |  | The workbook is readable and lists the PM5560 (column L), but it states neither the address base nor the word order (c02-schneider-base-wordorder). |
| Siemens | SENTRON PAC2200 | needs-check |  |  | Address base only inferable and multi-register word order unstated (c02-siemens-word-order). |
| Siemens | SENTRON PAC3120 | needs-check |  |  | Same as PAC2200 (c02-siemens-word-order). |
| Siemens | SENTRON PAC3220 | needs-check |  |  | Same as PAC2200 (c02-siemens-word-order). |

## 3. Grid-tied PV inverters

| Vendor | Model | Status | Contract | Points | Notes |
|---|---|---|---|---|---|
| Fronius | Primo 3.0-1 | mapped | [fronius/primo-3-0-1/sunspec-int-sf.omb.yaml](../devices/fronius/primo-3-0-1/sunspec-int-sf.omb.yaml) | 20 | Address base, not-available sentinels, sunssf signedness, F_ModelType values and the St/StVnd codes are checked against the pinned Datamanager manual. |
| Fronius | Primo 4.0-1 | mapped | [fronius/primo-4-0-1/sunspec-int-sf.omb.yaml](../devices/fronius/primo-4-0-1/sunspec-int-sf.omb.yaml) | 20 | Address base, not-available sentinels, sunssf signedness, F_ModelType values and the St/StVnd codes are checked against the pinned Datamanager manual. |
| Fronius | Primo 5.0-1 | mapped | [fronius/primo-5-0-1/sunspec-int-sf.omb.yaml](../devices/fronius/primo-5-0-1/sunspec-int-sf.omb.yaml) | 20 | Address base, not-available sentinels, sunssf signedness, F_ModelType values and the St/StVnd codes are checked against the pinned Datamanager manual. |
| Schneider Electric | Conext CL 18000NA | blocked |  |  | Register map and application note return 403 to the corpus client (Akamai). |
| Schneider Electric | Conext CL 25000NA | blocked |  |  | Register map and application note return 403 to the corpus client (Akamai). |
| Schneider Electric | Conext CL 20000E | blocked |  |  | Register map and application note return 403 to the corpus client (Akamai). |
| SMA | SB3.0-1AV-41 | needs-check |  |  | In scope of SunSpecModbus-TI-en-11 from firmware 4.00.23.R, but the vendor document requires SunSpec model discovery to locate any point (question c03-sma-sunspec-discovery). |
| SMA | SB5.0-1AV-41 | needs-check |  |  | In scope of SunSpecModbus-TI-en-11 from firmware 4.00.23.R, but the vendor document requires SunSpec model discovery to locate any point (question c03-sma-sunspec-discovery). |
| SMA | STP5.0-3AV-40 | needs-check |  |  | In scope of SunSpecModbus-TI-en-11 from firmware 4.00.02.R, but the vendor document requires SunSpec model discovery to locate any point (question c03-sma-sunspec-discovery). |
| SolarEdge | SE3000H-US | blocked |  |  | SunSpec technical note and model-scope datasheet return 403 (Cloudflare challenge). |
| SolarEdge | SE5000H-US | blocked |  |  | SunSpec technical note and model-scope datasheet return 403 (Cloudflare challenge). |
| SolarEdge | SE6000H-US | blocked |  |  | SunSpec technical note and model-scope datasheet return 403 (Cloudflare challenge). |
| Solis | S6-GR1P4K | mapped | [solis/s6-gr1p4k/telemetry.omb.yaml](../devices/solis/s6-gr1p4k/telemetry.omb.yaml) | 17 | Vendor scope: Solis grid-connected inverters of all power ranges manufactured after mid-2023; |
| Solis | S6-GR1P5K | mapped | [solis/s6-gr1p5k/telemetry.omb.yaml](../devices/solis/s6-gr1p5k/telemetry.omb.yaml) | 17 | Vendor scope: Solis grid-connected inverters of all power ranges manufactured after mid-2023; |
| Solis | S6-GR1P6K | mapped | [solis/s6-gr1p6k/telemetry.omb.yaml](../devices/solis/s6-gr1p6k/telemetry.omb.yaml) | 17 | Vendor scope: Solis grid-connected inverters of all power ranges manufactured after mid-2023; |

## 4. Battery energy storage interfaces

| Vendor | Model | Status | Contract | Points | Notes |
|---|---|---|---|---|---|
| Fronius | Symo GEN24 6.0 Plus | mapped | [fronius/symo-gen24-6-0-plus/storage.omb.yaml](../devices/fronius/symo-gen24-6-0-plus/storage.omb.yaml) | 18 | Valid when "SunSpec Model Type" = int+SF and a battery is configured (ROW map). |
| Fronius | Symo GEN24 8.0 Plus | mapped | [fronius/symo-gen24-8-0-plus/storage.omb.yaml](../devices/fronius/symo-gen24-8-0-plus/storage.omb.yaml) | 18 | Valid when "SunSpec Model Type" = int+SF and a battery is configured (ROW map). |
| Fronius | Symo GEN24 10.0 Plus | mapped | [fronius/symo-gen24-10-0-plus/storage.omb.yaml](../devices/fronius/symo-gen24-10-0-plus/storage.omb.yaml) | 18 | Valid when "SunSpec Model Type" = int+SF and a battery is configured (ROW map). |
| OutBack Power | Radian GS4048A | needs-check |  |  | Block-relative offsets only (split-phase Radian block 64115, Table 7); |
| OutBack Power | Radian GS8048A | needs-check |  |  | Same as GS4048A. |
| OutBack Power | FXR3048A | needs-check |  |  | Uses the single-phase Radian block (Table 12) and Radian configuration block (Table 11) per page 1; |
| Schneider Electric | Conext SW 2524 230 | mapped | [schneider-electric/conext-sw-2524-230/status.omb.yaml](../devices/schneider-electric/conext-sw-2524-230/status.omb.yaml) | 16 | Selected (all single-register uint16): Device State (enum, 255 "Data Not Available" as invalid), Device Present, Active Faults/Warnings flags, Fault Bitmap 0-2 and Warning Bitmap 0 (flags, Reserved bits omitted), Inverter Status and Charger Status (enums from sections 7 and 8), Battery Temperature (scale 0.01, offset -273), Charge DC Power Percentage, AC1 and Load AC frequency, Maximum Charge Rate and Maximum Discharge Current (rw rows read only). |
| Schneider Electric | Conext SW 4024 230 | mapped | [schneider-electric/conext-sw-4024-230/status.omb.yaml](../devices/schneider-electric/conext-sw-4024-230/status.omb.yaml) | 16 | Selected (all single-register uint16): Device State (enum, 255 "Data Not Available" as invalid), Device Present, Active Faults/Warnings flags, Fault Bitmap 0-2 and Warning Bitmap 0 (flags, Reserved bits omitted), Inverter Status and Charger Status (enums from sections 7 and 8), Battery Temperature (scale 0.01, offset -273), Charge DC Power Percentage, AC1 and Load AC frequency, Maximum Charge Rate and Maximum Discharge Current (rw rows read only). |
| Schneider Electric | Conext SW 4048 230 | needs-check |  |  | Not in Table 1 (Applicable Products) of 503-0244-01-01 Revision A.4; |
| SMA | SCS-1900 | blocked |  |  | See c04-sma-nda-terms. |
| SMA | SCS-2200 | blocked |  |  | See c04-sma-nda-terms. |
| SMA | SCS-2475 | blocked |  |  | See c04-sma-nda-terms. |
| Victron Energy | MultiPlus-II | mapped | [victron/multiplus-ii/vebus.omb.yaml](../devices/victron/multiplus-ii/vebus.omb.yaml) | 16 | Reached only through a GX device (gateway); |
| Victron Energy | Quattro | mapped | [victron/quattro/vebus.omb.yaml](../devices/victron/quattro/vebus.omb.yaml) | 16 | Reached only through a GX device (gateway); |
| Victron Energy | EasySolar-II GX | mapped | [victron/easysolar-ii-gx/vebus.omb.yaml](../devices/victron/easysolar-ii-gx/vebus.omb.yaml) | 16 | Same vebus layout, served by the built-in GX device; |

## 5. Transformer monitoring and tap-changer controllers

| Vendor | Model | Status | Contract | Points | Notes |
|---|---|---|---|---|---|
| COMEM | eOTI | needs-check |  |  | Register table without function code, address base, type or scale; |
| COMEM | eWTI | needs-check |  |  | Same Appendix A table as eOTI; |
| COMEM | CU eOLI | needs-check |  |  | Register table without function code, address base, type or scale; |
| Maschinenfabrik Reinhausen | TAPCON 230 AVT | mapped | [reinhausen/tapcon-230-avt/status.omb.yaml](../devices/reinhausen/tapcon-230-avt/status.omb.yaml) | 14 | Discrete inputs (raise/lower output, auto mode, local/remote, limit messages, alarm relay, function monitoring, power-flow direction), tap position and the LSW-first operation counter. |
| Maschinenfabrik Reinhausen | 250 | mapped | [reinhausen/tapcon-250/status.omb.yaml](../devices/reinhausen/tapcon-250/status.omb.yaml) | 16 | Input status bits, tap position (FC 04) and two holding-register enums documented for FC 03. |
| Maschinenfabrik Reinhausen | 260 | mapped | [reinhausen/tapcon-260/status.omb.yaml](../devices/reinhausen/tapcon-260/status.omb.yaml) | 11 | Discrete inputs and the tap position. |
| Qualitrol | 509ITM | blocked |  |  | Source returns HTTP 403 (c05-qualitrol-vercel-403). |
| Qualitrol | AKM345 Gen 3 | blocked |  |  | Source returns HTTP 403 (c05-qualitrol-vercel-403). |
| Qualitrol | T/Guard Link Rev B | blocked |  |  | Source returns HTTP 403 (c05-qualitrol-vercel-403). |
| TECSYSTEM | NT935 AD | mapped | [tecsystem/nt935-ad/telemetry.omb.yaml](../devices/tecsystem/nt935-ad/telemetry.omb.yaml) | 16 | Model and firmware strings, CPU error and relay bits, four channel temperatures (i16, Cel), channel 1 maximum and set points, and the four channel status bytes plus the channel 1 story byte (masked halves of one register, shared flag sets). |
| TECSYSTEM | NT935 ETH | mapped | [tecsystem/nt935-eth/telemetry.omb.yaml](../devices/tecsystem/nt935-eth/telemetry.omb.yaml) | 16 | Same map as NT935 AD over Modbus TCP; |
| TECSYSTEM | T1048 with Modbus | mapped | [tecsystem/t1048/telemetry.omb.yaml](../devices/tecsystem/t1048/telemetry.omb.yaml) | 16 | Same register addresses as NT935, but different ranges (-23 to 228 degC) and the fault relay bit reads "1=No Fault". |
| Vaisala | OPT100 | mapped | [vaisala/opt100/telemetry.omb.yaml](../devices/vaisala/opt100/telemetry.omb.yaml) | 20 | Status bits (mask 1 + enum), present-value caution and alarm bit fields, twelve present f32 values (eight gases, TDCG, moisture, chamber temperature, relative moisture, TGP), the u32 test value and one unscaled 16-bit gas value with the 0x8000 sentinel. |
| Vaisala | MHT410 | mapped | [vaisala/mht410/telemetry.omb.yaml](../devices/vaisala/mht410/telemetry.omb.yaml) | 10 | H2 averages, oil moisture (relative and ppmw) and oil temperature as f32, their 16-bit integer copies (x10 scaled, 0x8000 = not available) and the device status bits. |
| Vaisala | MMT162 | mapped | [vaisala/mmt162/telemetry.omb.yaml](../devices/vaisala/mmt162/telemetry.omb.yaml) | 7 | Temperature, water activity, moisture in oil (ppm, model dependent), fault status, the 32-bit error code and the two oil coefficients (read/write in the device, read-only here). |

## 6. Protection relays

| Vendor | Model | Status | Contract | Points | Notes |
|---|---|---|---|---|---|
| ABB | REF615 | mapped | [abb/ref615/protection.omb.yaml](../devices/abb/ref615/protection.omb.yaml) | 7 | Pinned to REF615 Ver. 3.0, standard configurations FE01-FE08; |
| ABB | REM615 | mapped | [abb/rem615/protection.omb.yaml](../devices/abb/rem615/protection.omb.yaml) | 7 | Pinned to REM615 Ver. 2.0, standard configuration ME03; |
| ABB | RET615 | mapped | [abb/ret615/protection.omb.yaml](../devices/abb/ret615/protection.omb.yaml) | 19 | Pinned to RET615 ANSI Ver. |
| Fanox | SIL-A | mapped | [fanox/sil-a/protection.omb.yaml](../devices/fanox/sil-a/protection.omb.yaml) | 9 | Two-register state words (FC 03) and the 88-character model/version string. |
| Fanox | SIA-C | mapped | [fanox/sia-c/protection.omb.yaml](../devices/fanox/sia-c/protection.omb.yaml) | 11 | The 52 (breaker) and 49 (thermal) words are marked (*) "Depending on model"; |
| Fanox | SIA-B Specific CT | mapped | [fanox/sia-b-specific-ct/protection.omb.yaml](../devices/fanox/sia-b-specific-ct/protection.omb.yaml) | 8 | This manual has no breaker word, so no mask point. |
| Littelfuse | SE-330 | blocked |  |  | Publisher returns 403 to the corpus client (c06-littelfuse-akamai-403). |
| Littelfuse | MPU-32 | blocked |  |  | Publisher returns 403 to the corpus client (c06-littelfuse-akamai-403). |
| Littelfuse | FPU-32 | blocked |  |  | Publisher returns 403 to the corpus client (c06-littelfuse-akamai-403). |
| Schneider Electric | Sepam S20 | mapped | [schneider-electric/sepam-s20/protection.omb.yaml](../devices/schneider-electric/sepam-s20/protection.omb.yaml) | 13 | Check-word flags, TS words 0101 and 0103 (TS bits marked for S20 only), phase/residual and tripping currents, cumulative breaking current (kA2) and number of operations (the selection table marks it v). |
| Schneider Electric | Sepam T20 | mapped | [schneider-electric/sepam-t20/protection.omb.yaml](../devices/schneider-electric/sepam-t20/protection.omb.yaml) | 18 | Adds the 49 RMS TS bits, TS49-TS64 (38/49T), thermal capacity used, running hours, time before overload trip and the eight 16 S temperatures as one count-8 array (MET148-2 module, marked v). |
| Schneider Electric | Sepam M20 | mapped | [schneider-electric/sepam-m20/protection.omb.yaml](../devices/schneider-electric/sepam-m20/protection.omb.yaml) | 20 | Like T20, plus the motor TS bits (37, 48/51LR/14, 66) and starting time/current. |
| Siemens | 7SJ80 | mapped | [siemens/7sj80/protection.omb.yaml](../devices/siemens/7sj80/protection.omb.yaml) | 16 | Indications follow table 1-1. |
| Siemens | 7SK80 | mapped | [siemens/7sk80/protection.omb.yaml](../devices/siemens/7sk80/protection.omb.yaml) | 16 | Indications follow table 1-2 (adds 46, 66 and start-up supervision); |
| Siemens | 7RW80 | mapped | [siemens/7rw80/protection.omb.yaml](../devices/siemens/7rw80/protection.omb.yaml) | 12 | Indications follow table 1-3 (27, 59, 81). |

## 7. Remote I/O

| Vendor | Model | Status | Contract | Points | Notes |
|---|---|---|---|---|---|
| Advantech | ADAM-6050 | needs-check |  |  | Address base unresolved (c07-adam-address-base); |
| Advantech | ADAM-6051 | needs-check |  |  | Same appendix and the same two ambiguities as the ADAM-6050. |
| Advantech | ADAM-6060 | needs-check |  |  | Same appendix and the same two ambiguities; |
| AutomationDirect | SIO-MB12CDR | mapped | [automationdirect/sio-mb12cdr/io.omb.yaml](../devices/automationdirect/sio-mb12cdr/io.omb.yaml) | 19 | 8 input and 4 output coils, System Flags (40011) as flags, 4 input frequencies (u16, 0.01 Hz), Firmware [0]/[1]. |
| AutomationDirect | SIO-MB16CDD2 | mapped | [automationdirect/sio-mb16cdd2/io.omb.yaml](../devices/automationdirect/sio-mb16cdd2/io.omb.yaml) | 19 | 8 input and 8 output coils, System Flags with the short-circuit alarm bit, Firmware [0]/[1]. |
| AutomationDirect | SIO-MB08THMS | mapped | [automationdirect/sio-mb08thms/io.omb.yaml](../devices/automationdirect/sio-mb08thms/io.omb.yaml) | 20 | 8 temperatures as i16 x 0.1 Cel, valid only for thermocouple input types with Celsius degree units (the defaults; |
| Brainboxes | ED-516 | mapped | [brainboxes/ed-516/inputs.omb.yaml](../devices/brainboxes/ed-516/inputs.omb.yaml) | 32 | Already mapped before this class run. |
| Brainboxes | ED-538 | mapped | [brainboxes/ed-538/io.omb.yaml](../devices/brainboxes/ed-538/io.omb.yaml) | 20 | 8 discrete inputs, 4 output coils (read back with FC 1), 8 16-bit counters (input registers). |
| Brainboxes | ED-588 | mapped | [brainboxes/ed-588/io.omb.yaml](../devices/brainboxes/ed-588/io.omb.yaml) | 16 | 8 discrete inputs and 8 output coils. |
| ICP DAS | ET-2251 | mapped | [icp-das/et-2251/io.omb.yaml](../devices/icp-das/et-2251/io.omb.yaml) | 16 | DI states and latches (discrete inputs), counter/frequency enables (coils, read-only here), 32-bit counters and frequencies low word first (frequency x 1/1000, unit not stated in the row: c07-icp-das-frequency-unit), channel counts and module status. |
| ICP DAS | ET-2252 | needs-check |  |  | Universal DIO; nDI/nDO "Depend on the configuration" (c07-icp-das-et-2252-udio). |
| ICP DAS | ET-2268 | mapped | [icp-das/et-2268/io.omb.yaml](../devices/icp-das/et-2268/io.omb.yaml) | 13 | Output coils read back, PWM/power-on/safe-value settings (read-only here), DO channel count, min-switching and auto-off times (s), module status. |
| Moxa | ioLogik E1210 | mapped | [moxa/iologik-e1210/io.omb.yaml](../devices/moxa/iologik-e1210/io.omb.yaml) | 7 | DI states, 32-bit counters (high/low word), overflow and counter run flags, model/device name strings, firmware version bytes. |
| Moxa | ioLogik E1212 | mapped | [moxa/iologik-e1212/io.omb.yaml](../devices/moxa/iologik-e1212/io.omb.yaml) | 12 | As E1210 plus DO states (coils), pulse/P2P status, pulse on/off widths (u16, ms). |
| Moxa | ioLogik E1240 | mapped | [moxa/iologik-e1240/io.omb.yaml](../devices/moxa/iologik-e1240/io.omb.yaml) | 8 | Raw AI values with min/max, AI_status enum, AI_mode range-code enum, identification. |

## 8. Motor variable-frequency drives

| Vendor | Model | Status | Contract | Points | Notes |
|---|---|---|---|---|---|
| ABB | ACS580 | needs-check |  |  | Needs the ACS580 firmware manual next to FSCA-01; |
| ABB | ACH580 | needs-check |  |  | Needs the ACH580 firmware manual next to FSCA-01; |
| ABB | ACS880 | needs-check |  |  | Needs the ACS880 firmware manual next to FSCA-01; |
| AutomationDirect | GS20 | mapped | [automationdirect/gs20/status.omb.yaml](../devices/automationdirect/gs20/status.omb.yaml) | 12 | Fault code and warning code are the low and high bytes of 2100h as plain numbers. |
| AutomationDirect | GS30 | mapped | [automationdirect/gs30/status.omb.yaml](../devices/automationdirect/gs30/status.omb.yaml) | 12 | Identical status map to the GS20. |
| AutomationDirect | GS4 | mapped | [automationdirect/gs4/status.omb.yaml](../devices/automationdirect/gs4/status.omb.yaml) | 9 | 2100h error code is an enum of 71 codes parsed from the two-column list (reserved codes skipped). |
| Danfoss | FC 51 | mapped | [danfoss/fc-51/status.omb.yaml](../devices/danfoss/fc-51/status.omb.yaml) | 10 | Status word (FC profile), power, motor voltage, frequency, motor current, DC link voltage (the manual states no unit), alarm word and warning word (flags), running hours and kWh counter. |
| Danfoss | FC 301 | needs-check |  |  | Address base ambiguous in the Design Guide; |
| Danfoss | FC 302 | needs-check |  |  | Address base ambiguous in the Design Guide; |
| Rockwell Automation | PowerFlex 4 | blocked |  |  | Source blocked (HTTP 403); |
| Rockwell Automation | PowerFlex 40 | blocked |  |  | Source blocked (HTTP 403); |
| Rockwell Automation | PowerFlex 400 | blocked |  |  | Source blocked (HTTP 403); |
| Schneider Electric | ATV320 | mapped | [schneider-electric/atv320/status.omb.yaml](../devices/schneider-electric/atv320/status.omb.yaml) | 11 | ETA (CiA402 flags), HMIS drive state (28 values), LFT last fault (61 values), RFR, RFRD, OTR, UOP, OPR, ULN, THD and LCR. |
| Schneider Electric | ATV340 | mapped | [schneider-electric/atv340/status.omb.yaml](../devices/schneider-electric/atv340/status.omb.yaml) | 16 | As ATV320 without LCR, plus VBUS and the input energy registers IC0 to IC4 (resettable, R/WS; |
| Schneider Electric | ATV630 | mapped | [schneider-electric/atv630/status.omb.yaml](../devices/schneider-electric/atv630/status.omb.yaml) | 16 | Same point set as ATV340 from the ATV600 workbook; |

## 9. Generator-set controllers

| Vendor | Model | Status | Contract | Points | Notes |
|---|---|---|---|---|---|
| Datakom | D-300 | mapped | [datakom/d-300/telemetry.omb.yaml](../devices/datakom/d-300/telemetry.omb.yaml) | 13 | Genset frequency 10339 (x100), battery voltage 10341 (x100), oil pressure 10361 (x10, bar), fuel level 10363 (x10, %), magnetic pickup 10375 and engine rpm 10376 (/min), operation status 10604 (enum 0-25), unit mode 10605 (enum), device identity 10609 (enum, constant), and four 16-bit words of the shutdown (10504-10519) and warning (10536-10551) bit arrays (alarm bits 48-63 and 96-111, page 17). |
| Datakom | D-500 | mapped | [datakom/d-500/telemetry.omb.yaml](../devices/datakom/d-500/telemetry.omb.yaml) | 13 | Same rows as D-300; unit mode value 2 is "RUN mode (D500)". |
| Datakom | D-700 | mapped | [datakom/d-700/telemetry.omb.yaml](../devices/datakom/d-700/telemetry.omb.yaml) | 13 | Same rows as D-300; unit mode value 2 is "MANUAL mode (D700)". |
| DEIF | AGC-3 | mapped | [deif/agc-3/telemetry.omb.yaml](../devices/deif/agc-3/telemetry.omb.yaml) | 19 | AGC-3 SW 3.6x.x or later with option H2. |
| DEIF | AGC 111 | mapped | [deif/agc-111/telemetry.omb.yaml](../devices/deif/agc-111/telemetry.omb.yaml) | 20 | AGC 100 SW 4.0x.x or later with option H2 (the document lists "AGC 100" in its product list and names AGC 111 only as a table column). |
| DEIF | AGC 110 | mapped | [deif/agc-110/telemetry.omb.yaml](../devices/deif/agc-110/telemetry.omb.yaml) | 7 | AGC 100 SW 4.0x.x or later with option H2. |
| Kohler | Decision-Maker 550 | needs-check |  |  | Address base not stated (c09-kohler-address-base). |
| Kohler | Decision-Maker 3500 | needs-check |  |  | Address base not stated (c09-kohler-address-base). |
| Kohler | Decision-Maker 6000 | needs-check |  |  | Address base not stated (c09-kohler-address-base). |
| SmartGen | HGM6120T | needs-check |  |  | The two function 03H tables claim the same addresses (c09-smartgen-hgm6120t-overlapping-tables), so no address can be trusted without a device check. |
| SmartGen | HGM9510 | mapped | [smartgen/hgm9510/telemetry.omb.yaml](../devices/smartgen/hgm9510/telemetry.omb.yaml) | 14 | Common alarm/mode bits 0000 and shutdown alarms 0001 (Table 2), mains frequency 0064 (ratio 0.01, Hz), generator voltages UAB/UA/UB/UC 0075, 0078-0080 (16-bit signed, V), currents 0095-0097 (16-bit unsigned, A), generator status 0189 (Table 16) and mains status 0195 (Table 19) enums, accumulated running hours 0199 (h), and the "A Gen Power kWh" counter 0274-0275 (32-bit signed, low word first, kW.h). |
| SmartGen | HGM9530N | mapped | [smartgen/hgm9530n/telemetry.omb.yaml](../devices/smartgen/hgm9530n/telemetry.omb.yaml) | 17 | Common alarm/mode bits 0000, generator voltages UAB/UA/UB/UC 0140, 0146, 0148, 0150 (32-bit, low word first, *10), frequency 0155 (*100), currents 0166-0168 (*10), total active power 0180-0181 (signed 32-bit, *10), average power factor 0201 (signed, *1000), engine speed 0212, battery voltage 0213 (*10), generator status 0260 and breaker status 0264 enums (forms 5.5 and 5.7, p.26), total running hours 0270 (h) and start count 0273. |
| Woodward | easYgen-3400 | mapped | [woodward/easygen-3400/telemetry.omb.yaml](../devices/woodward/easygen-3400/telemetry.omb.yaml) | 18 | Protocol 5010 applies when parameter 3184 is 5010 (the default). |
| Woodward | easYgen-3500 | mapped | [woodward/easygen-3500/telemetry.omb.yaml](../devices/woodward/easygen-3500/telemetry.omb.yaml) | 18 | Same layout and points as easYgen-3400 (one manual for both models, no per-model rows selected). |
| Woodward | easYgen-3200XT | mapped | [woodward/easygen-3200xt/telemetry.omb.yaml](../devices/woodward/easygen-3200xt/telemetry.omb.yaml) | 20 | Covers 3200XT-P1 and 3200XT-P1-LT, release 2.17 or higher; |

## 10. PV irradiance and reference sensors

| Vendor | Model | Status | Contract | Points | Notes |
|---|---|---|---|---|---|
| Apogee Instruments | SP-422 | mapped | [apogee-instruments/sp-422/telemetry.omb.yaml](../devices/apogee-instruments/sp-422/telemetry.omb.yaml) | 8 | Irradiance and detector voltage as f32 and as decimal-shifted i16 ("multiplied by 10/100"), device status enum, firmware/model/serial floats. |
| Apogee Instruments | SP-522 | mapped | [apogee-instruments/sp-522/telemetry.omb.yaml](../devices/apogee-instruments/sp-522/telemetry.omb.yaml) | 9 | Same layout as SP-422 plus heater status (integer register 57, read-only here). |
| Apogee Instruments | SP-722 | mapped | [apogee-instruments/sp-722/telemetry.omb.yaml](../devices/apogee-instruments/sp-722/telemetry.omb.yaml) | 10 | Incident and reflected irradiance, detector voltages and albedo as f32, heater on/off, device status. |
| EKO Instruments | MS-40S | mapped | [eko-instruments/ms-40s/s-series.omb.yaml](../devices/eko-instruments/ms-40s/s-series.omb.yaml) | 14 | Selected Modbus profile: register type S-series (register 103, factory default). |
| EKO Instruments | MS-60S | mapped | [eko-instruments/ms-60s/s-series.omb.yaml](../devices/eko-instruments/ms-60s/s-series.omb.yaml) | 14 | Selected Modbus profile: S-series (default). |
| EKO Instruments | MS-80S | mapped | [eko-instruments/ms-80s/s-series.omb.yaml](../devices/eko-instruments/ms-80s/s-series.omb.yaml) | 16 | Selected Modbus profile: S-series (default). |
| Hukseflux | SR20-D2 | mapped | [hukseflux/sr20-d2/telemetry.omb.yaml](../devices/hukseflux/sr20-d2/telemetry.omb.yaml) | 12 | Compensated and uncompensated irradiance (S32, 0.01 W/m2), body temperature, thermopile resistance (invalid 0 until a measurement is triggered via coil 2), irradiance scaling factor (unconverted, see c10-scaling-factor-register), sensor voltage (1e-9 V), serial, sensitivity float (uV.m2/W), response time, calibration date, firmware and hardware version. |
| Hukseflux | SR15-D1A3 | needs-check |  |  | The SR15 digital series manual covers SR15-D1 and SR15-D2A2; |
| Hukseflux | SR30-M2-D1 | needs-check |  |  | Word order of 32-bit registers not stated (c10-sr30-word-order). |
| IMT Technology | Si-RS485TC-T-MB | mapped | [imt-technology/si-rs485tc-t-mb/telemetry.omb.yaml](../devices/imt-technology/si-rs485tc-t-mb/telemetry.omb.yaml) | 4 | Irradiance (0.1 W/m2), cell temperature (i16, 0.1 °C) and the two compatibility cell temperature registers (u16 with offsets -25 and -100). |
| IMT Technology | Si-RS485TC-2T-MB | mapped | [imt-technology/si-rs485tc-2t-mb/telemetry.omb.yaml](../devices/imt-technology/si-rs485tc-2t-mb/telemetry.omb.yaml) | 5 | As Si-RS485TC-T-MB plus external temperature 1 (register 8, ambient on this type). |
| IMT Technology | Si-RS485TC-T-Tm-MB | mapped | [imt-technology/si-rs485tc-t-tm-mb/telemetry.omb.yaml](../devices/imt-technology/si-rs485tc-t-tm-mb/telemetry.omb.yaml) | 5 | As Si-RS485TC-T-MB plus external temperature 1 (register 8, PV module temperature on this type). |
| Kipp & Zonen | SMP3 | mapped | [kipp-zonen/smp3/telemetry.omb.yaml](../devices/kipp-zonen/smp3/telemetry.omb.yaml) | 18 | Data model 107. Device type enum, operational mode enum, status flags (bits 0-12), scale factor, compensated and raw irradiance (unconverted, c10-negated-scale-factor), body temperature, supply voltage, sensor input voltage (i32, MSB first), error code, on-time (u32 from TIMEH/TIMEL), batch, serial, software and hardware version, error flag and calibration error discrete inputs. |
| Kipp & Zonen | SMP6 | mapped | [kipp-zonen/smp6/telemetry.omb.yaml](../devices/kipp-zonen/smp6/telemetry.omb.yaml) | 18 | Same layout as SMP3. |
| Kipp & Zonen | SMP10 | mapped | [kipp-zonen/smp10/telemetry.omb.yaml](../devices/kipp-zonen/smp10/telemetry.omb.yaml) | 18 | Same layout as SMP3. |

## Outside the target roster

| Vendor | Model | Class | Contract | Points | Notes |
|---|---|---|---|---|---|
| Victron Energy | Cerbo GX (GX system service) | 4 | [victron/cerbo-gx/system.omb.yaml](../devices/victron/cerbo-gx/system.omb.yaml) | 4 | Pilot contract from the pinned dbus_modbustcp attributes.csv; |
