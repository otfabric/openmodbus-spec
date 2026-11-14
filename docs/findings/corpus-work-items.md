# Corpus work items

Generated from [corpus/roster.yaml](../../corpus/roster.yaml) by `corpus/roster.py`; do not edit by hand. Each item names its evidence (document, page or row, vendor address) and who has to act.

Spec-gap candidates are inputs to the maintainer's decisions in [PROPOSAL.md](../PROPOSAL.md); none is agreed. A candidate shows a reviewed source row and a case the current draft cannot express.

| Kind | Open items |
|---|---|
| Spec-gap candidates | 15 |
| Questions on the draft | 42 |
| Document ambiguities | 74 |
| Vendor errata | 38 |
| Model scope | 12 |
| Source access | 13 |
| Tooling | 18 |

## Themes

The spec-gap candidates and questions, grouped by the draft decision they bear on. A theme that recurs across classes is stronger evidence than a single vendor.

| Theme | Decisions | Classes | Items |
|---|---|---|---|
| Validity decided by another register or bit | D6 (invalid), D9 | 1, 4, 5, 6, 7 | 5 |
| Scale, unit, word order or layout selected by configuration | D3 (variants), D5, D9, D13 | 1, 3, 6, 7, 8, 9, 10 | 11 |
| Conversions the linear model cannot express | D6, D9 | 1, 2, 8, 10 | 5 |
| Values composed from several registers or fields | D6, D7 | 1, 2, 3, 5, 8, 9 | 7 |
| Sentinels beyond exact raw values | D6 (invalid, section 6.6) | 1, 3, 5, 6, 9 | 6 |
| Enums and flags outside plain integer fields | D6 (section 6.5), D7 | 1, 2, 6, 8, 9 | 5 |
| Discovery, gateway unit IDs and address bases | D3, D4, D12 | 3, 4, 5, 10 | 6 |
| Request shape, coherence and timing | D9 (stability), D10 | 1, 4, 5, 10 | 5 |
| Units outside UCUM | D13 | 1, 3, 6 | 3 |
| Arrays, strings, records and device tests | D3, D7, D14 | 1, 5, 6, 7 | 4 |

### Validity decided by another register or bit

A value is valid only when a status bit, a mode or a device-level flag says so. invalid lists raw sentinels of the point itself and cannot reference another point.

- `c01-validity-bit-datetime` (spec-gap, class 1, Schneider Electric; ABB): Packed 4-word DATETIME with an in-band validity bit; fields fit masks, but neither a composite timestamp nor bit-driven validity is expressible.
- `c04-schneider-device-present-gate` (question, class 4, Schneider Electric): A device-level "data valid" register invalidates all other points, which the draft cannot express.
- `c05-tecsystem-disabled-channel-zero` (spec-gap, class 5, TECSYSTEM): A disabled channel reads temperature 0000 (0 degC); validity depends on a bit in another register.
- `c06-siemens-data-invalid-flag` (question, class 6, Siemens): The validity of every value depends on bit 15 "Data invalid" of the diagnostics register 40129.
- `c07-validity-from-status-register` (spec-gap, class 7, AutomationDirect): A channel value's validity is flagged in a separate status register (or depends on a mode), which `invalid` sentinels cannot express.

### Scale, unit, word order or layout selected by configuration

A configuration register or device setting changes how other registers decode. variants.match covers firmware and hardware only, and exponent10 references take the raw exponent only.

- `c01-configurable-word-order` (question, class 1, Eastron): Float word order is a runtime setting (Register Order); contracts assume the default.
- `c03-config-dependent-layout` (question, class 3, Fronius): Layout depends on a configuration register (F_ModelType) and Solis scope on production date; variants.match has only firmware/hardware.
- `c06-configured-default-scaling` (question, class 6, Siemens): Scale factors are defaults that the device configuration can change and that no register reports.
- `c07-enum-selected-scale-unit` (spec-gap, class 7, AutomationDirect): The scale and unit of a temperature register are selected by enum configuration registers, which 0.1 cannot express.
- `c08-schneider-cmi-frequency-unit` (spec-gap, class 8, Schneider Electric): A control-word bit selects the output frequency scale, one option relative to another parameter.
- `c08-schneider-current-decade` (question, class 8, Schneider Electric): An enum register selects a power-of-ten scale through non-exponent codes.
- `c09-kohler-unit-system-register` (spec-gap, class 9, Kohler): A readable register (400139 Metric Units) switches the unit of other registers between metric and English.
- `c09-woodward-exponent-stability` (question, class 9, Woodward): The exponent registers are configuration parameters; their stability is left at the default.
- `c10-config-selected-unit` (question, class 10, EKO Instruments): Internal temperature unit (°C/°F/K) is chosen by a device setting that the S-series map does not expose.
- `c10-register-type-profiles` (question, class 10, EKO Instruments): Register 103 switches registers 0-49 between four maps (S-, M-, SMP-, SRD-series); only the default S-series is mapped.
- `c10-scaling-factor-register` (question, class 10, Hukseflux): Registers 8 and 9 "Scaling factor irradiance/temperature, Default = 100" have no stated effect on the data registers.

### Conversions the linear model cannot express

Folded four-quadrant power factor, ratios to other points or parameters, and scale factors that divide.

- `c01-folded-power-factor` (spec-gap, class 1, Schneider Electric): Power factor float folded into -2..+2 to encode the quadrant; no linear conversion recovers PF.
- `c02-schneider-4q-pf` (spec-gap, class 2, Schneider Electric): The four-quadrant float power factor needs a piecewise decode that the draft's linear conversion cannot express.
- `c02-janitza-short-ratio` (spec-gap, class 2, Janitza electronics): A short value must be multiplied by a transformer ratio held in two other float registers; the draft cannot express raw x pointA / pointB.
- `c08-abb-ratio-scaling` (spec-gap, class 8, ABB): Fieldbus actual values scale to another parameter (20000 = a speed or frequency parameter value).
- `c10-negated-scale-factor` (spec-gap, class 10, Kipp & Zonen): A scale-factor register that divides by 10^SF cannot be expressed; exponent10 references only multiply.

### Values composed from several registers or fields

Decimal splits (base 1000 or 10000), MSW/LSW counter pairs with decimal ranges, packed BCD, timestamps from two words, and statuses refined by a second register.

- `c01-bcd-setting` (spec-gap, class 1, Eastron): Packed BCD configuration word (four 1-byte BCD fields) has no type in the draft.
- `c02-schneider-mod10k` (question, class 2, Schneider Electric): Could not confirm whether any PM5000 register uses an INT64 MOD10K energy format.
- `c03-solis-composite-status` (question, class 3, Solis): Inverter status 3043 is subdivided by register 3029; the draft cannot express the combined meaning.
- `c05-comem-event-timestamp` (question, class 5, COMEM): Event time is Timestamp Hi + 2^16 x Timestamp Low seconds since 2014-01-01, with inverted register names.
- `c05-tapcon-230-avt-counter-words` (question, class 5, Maschinenfabrik Reinhausen): Operation Counter LSW/MSW rows each give the range 0..99999999.
- `c08-schneider-energy-decades` (spec-gap, class 8, Schneider Electric): Input energy is one value split over five registers in base 1000.
- `c09-smartgen-hgm6120t-split-counters` (question, class 9, SmartGen): Run hours, start count and energy are MSB/LSB register pairs with range 0-9999 each; the combination is not stated.

### Sentinels beyond exact raw values

Sentinel ranges, a sentinel in one word of a multi-word value, saturated (clamped) readings, not-available strings, and u64 sentinels above 2^53.

- `c01-msw-overflow-sentinel` (question, class 1, Carlo Gavazzi): Overflow is signalled by the most significant word alone (MSW == 7FFFh); invalid lists exact raw values only, so this needs 65536 entries.
- `c01-u64-sentinel-precision` (question, class 1, ABB): invalid: [18446744073709551615] on u64 points exceeds 2^53; JSON consumers parsing contracts as binary64 cannot match it.
- `c03-string-not-available` (question, class 3, Fronius): A not-available string is all zero registers; invalid only takes integers.
- `c05-mht410-saturation-codes` (question, class 5, Vaisala): 7FFFhex means "32767 or larger" and 8001hex "-32767 or smaller"; the draft has no saturated state.
- `c06-measurement-saturation` (question, class 6, Schneider Electric): Sepam and the ABB 615 series clamp over-range measurements to the format maximum; the draft has no "saturated" quality.
- `c09-kohler-dm3500-sentinel-ranges` (question, class 9, Kohler): "Data unknown" is a range of 32 raw values (0x7FE0-0x7FFF signed, 0xFFE0-0xFFFF unsigned).

### Enums and flags outside plain integer fields

Enumerations carried as floats, flag sets mixed with a bit field, a flag width the schema lacks, and bit lists declared signed.

- `c01-float-coded-enum` (question, class 1, Eastron): Settings are enumerations transported as IEEE floats; may enum apply to an f32 whose value is integral?
- `c02-janitza-rotation-float-enum` (question, class 2, Janitza electronics): The rotation field is a float carrying the codes 1, 0 and -1; §6.5 enums map raw integers only.
- `c06-flags-with-bit-field` (question, class 6, Schneider Electric): The Sepam check-word mixes a 4-bit field (mapping number, bits 3-0) with flags (bits 4-15); the draft cannot express both cleanly.
- `c08-flags-width` (question, class 8, AutomationDirect): Spec section 6.5 mentions a flag width, but the schema's flagSetDef has no width property.
- `c09-woodward-bitlist-int16` (question, class 9, Woodward): BITLIST registers declared int16 are read as u16 for mask and flags.

### Discovery, gateway unit IDs and address bases

SunSpec model chains that move, gateway-assigned unit IDs, data behind a vendor function code, and an address base read from a column header.

- `c03-fronius-sunspec-discovery` (question, class 3, Fronius): Vendor says SunSpec register addresses are not constant and models should be located by scanning.
- `c03-sma-sunspec-discovery` (question, class 3, SMA): SMA's SunSpec document gives no addresses; points can only be located by SunSpec model discovery.
- `c04-fronius-dynamic-model-chain` (question, class 4, Fronius): Absolute addresses are only valid for one configuration of the SunSpec model chain.
- `c04-victron-gateway-unit-id` (question, class 4, Victron Energy): Gateway-assigned unit IDs do not fit unitId.mode fixed/configurable/ignored.
- `c05-tecsystem-address-base` (question, class 5, TECSYSTEM): Addresses are taken as PDU addresses from the "Address LO (10)" column header.
- `c10-vendor-function-code` (question, class 10, IMT Technology): Serial number, firmware version and bus parameters are only available through vendor function code 0x46.

### Request shape, coherence and timing

A register whose meaning depends on the request length, safe gaps over defined points, multi-word and scale-factor coherence, and a power-up delay.

- `c01-request-shape-dependent-register` (spec-gap, class 1, Carlo Gavazzi; Eastron): A register returns a different quantity depending on the request length; the draft cannot hold both points.
- `c01-safe-gap-over-points` (question, class 1, ABB): A safe_gap range that covers defined points as well as holes.
- `c04-fronius-scale-factor-coherence` (question, class 4, Fronius): Auto-scaled scale factors change at runtime; a value and its _SF read in two requests can mismatch.
- `c05-mmt162-power-up-delay` (question, class 5, Vaisala): The guide says to wait five seconds after power-up before sending Modbus requests.
- `c10-coherent-multiword-read` (question, class 10, Hukseflux): Vendor requires the MSW and LSW of a 32-bit value in one request; the draft does not say a multi-register point is read in one request.

### Units outside UCUM

Reactive power (var) and per-unit quantities (multiples of rated current or voltage).

- `c01-var-unit` (question, class 1, ABB; Carlo Gavazzi; Eastron): UCUM has no var; the draft allows it with warning W006, the corpus builder rejects it, so reactive points carry no unit.
- `c03-reactive-power-unit` (spec-gap, class 3, Solis): UCUM has no var, so reactive power carries no machine-readable unit.
- `c06-per-unit-quantities` (question, class 6, ABB): Currents and voltages are given in multiples of the rated values (xIn, xUn); UCUM has no unit for that.

### Arrays, strings, records and device tests

Index bases for count arrays, odd-length strings, time-tagged event records, and vendor test registers as level-4 anchors.

- `c01-odd-length-string` (question, class 1, Carlo Gavazzi): 13-character serial number in 7 registers with the last low byte 'not to be used'.
- `c05-test-value-registers` (question, class 5, Vaisala): Vendor test registers with known constants could anchor level-4 device tests.
- `c06-time-tagged-records` (question, class 6, Schneider Electric): Every relay delivers time-tagged events and fault records through handshake structures that read-only flat points cannot express.
- `c07-count-array-index` (question, class 7, Moxa): Should point `count` arrays carry an index base or element names, as group repeats do?

## Spec-gap candidates

### `c01-request-shape-dependent-register`: A register returns a different quantity depending on the request length; the draft cannot hold both points.

- **Class 1, vendor:** Carlo Gavazzi; Eastron (EM511, EM530, EM540, SDM230, SDM630)
- **Owner:** maintainer
- **Decision:** D10 (read constraints); touches E002 (D14)
- **Evidence:** EM511 rev 1.8 p.13 Table 4.1-1 000Ah 'W dmd' INT32 (000Ah-000Bh) and p.16 section 4.5 000Bh 'Carlo Gavazzi Controls identification code' UINT16, 'limited to a word at a time'. EM530/EM540 v1.3 p.12 000Ah 'V L3-L1' INT32 and p.18 000Bh identification code. Eastron SDM230 v1.4 p.2 and SDM630 v1.8 p.2: 'will response to any single input or holding register read with an instrument type specific value'.
- **Detail:** ranges[].policy isolated (section 7) only restricts how a point is read; E002 still rejects an identification point at 11 overlapping an i32 at 10-11, and variants (5.6) select by firmware or hardware, not by request shape. The contracts here keep the identification code and drop W dmd / V L3-L1. Options: let an isolated range scope an overlap exemption, or a request-shape qualifier.
- **Proposed regression:** Contract with v_l3_l1 (i32, wordOrder little, input 10) and identification_code (u16, input 11, isolated 11/1) validates. FC04 11 count 1 -> [0x06E0] -> identification_code 1760 (em540dinav23xs1x); FC04 10 count 2 -> [0x0960, 0x0000] -> v_l3_l1 = 240.0 V with exponent10 -1.

### `c01-bcd-setting`: Packed BCD configuration word (four 1-byte BCD fields) has no type in the draft.

- **Class 1, vendor:** Eastron (SDM230)
- **Owner:** maintainer
- **Decision:** D6 (numeric model; section 11 reserved types)
- **Evidence:** SDM230 v1.4 p.4 holding 462721 (F500h): 'Demand interval, slide time, automatic scroll display interval (scroll Time), Backlight time', 'min-min-s-min', 'Data Format: BCD (length: 4 byte)'.
- **Detail:** Masks can isolate each byte but cannot turn 0x60 into 60. BCD is listed as reserved in section 11. The byte-to-field order (first field in the high byte of the first register) is my reading of 'min-min-s-min' and needs vendor confirmation. Not mapped.
- **Proposed regression:** FC03 0xF500 count 2 -> [0x6001, 0x0560] -> demand_interval 60 min, slide_time 1 min, scroll_time 5 s, backlight_time 60 min.

### `c01-folded-power-factor`: Power factor float folded into -2..+2 to encode the quadrant; no linear conversion recovers PF.

- **Class 1, vendor:** Schneider Electric (iEM3155, iEM3255, iEM3355)
- **Owner:** maintainer
- **Decision:** D6 (numeric model / conversion)
- **Evidence:** DOCA0005EN-16 p.67, 0x0C0B (register 3084) Total Power Factor Float32: '-1 < PF < 0 = Quad 2 ... -2 < PF < -1 = Quad 3 ... 0 < PF < 1 = Quad 1 ... 1 < PF < 2 = Quad 4'.
- **Detail:** The raw float is expressible; the quadrant (and the conventional PF magnitude) needs a piecewise transform (section 11 reserves conditional conversion). The doc states only the quadrant ranges; the magnitude formula (2 - x above 1, -2 - x below -1) is an inference to confirm.
- **Proposed regression:** f32 1.2 (0x3F99999A) -> quadrant 4, active power positive, capacitive (stated); PF 0.8 (inferred). f32 -1.2 -> quadrant 3 (stated); PF -0.8 (inferred).

### `c01-validity-bit-datetime`: Packed 4-word DATETIME with an in-band validity bit; fields fit masks, but neither a composite timestamp nor bit-driven validity is expressible.

- **Class 1, vendor:** Schneider Electric; ABB (iEM3155, iEM3255, iEM3355, B21)
- **Owner:** maintainer
- **Decision:** D6 (types; section 11) and section 6.6 validity
- **Evidence:** DOCA0005EN-16 p.56-57 DATETIME: word1 year b6:b0 (from 2000), word2 month b11:b8, WD b7:b5, day b4:b0, word3 SU b15, hour b12:b8, iV b7 ('Bit to 0 if this parameter is not valid'), minute b5:b0, word4 milliseconds; used at 0x0083 Date of Manufacture. ABB B21 p.75 8A00 Date/time: 6 bytes year..second, year offset shown only by the B23/B24 p.82 example (2010 -> 0x0A).
- **Detail:** Each field maps to a masked u16 (offset 2000 for the year), but quality depends on another bit (iV), which section 6.6 cannot express, and a timestamp needs all four words from one read (blocks.coherent only if the vendor guarantees it). Timestamps are reserved in section 11. Not mapped.
- **Proposed regression:** FC03 0x0083 count 4 -> [0x001A, 0x0B0D, 0x0E9E, 0x0000] -> 2026-11-13 14:30:00.000 valid; with word3 0x0E1E (iV = 0) -> invalid.

### `c02-janitza-short-ratio`: A short value must be multiplied by a transformer ratio held in two other float registers; the draft cannot express raw x pointA / pointB.

- **Class 2, vendor:** Janitza electronics (UMG 96RM, UMG 96RM-E, UMG 96RM-PN)
- **Owner:** maintainer
- **Decision:** D6, D9
- **Evidence:** DE PDF p.6: "Messwerte im Short-Format berücksichtigen nicht die eingestellten Wandlerverhältnisse, d.h. diese Messwerte sind mit dem entsprechenden Wandlerfaktor zu multiplizieren" (EN PDF p.5, same). Row: "Messwerte, Typ Short", 3530 SHORT V, Voltage U1 L1-N, resolution 0,1 (DE PDF p.20). Ratio rows (PDF p.14): 14 FLOAT V "Spannungswandler V1, prim.", 16 FLOAT V "Spannungswandler V1, sek."; current transformers at 10/12, 18/20 and so on.
- **Detail:** §6.4 allows a literal multiplier and an integer exponent10 that may reference a point; neither carries a ratio of two float points. The contracts expose the secondary value and point to the float register that already includes the ratio. A minimal extension would be `multiplier: {point: a, divideBy: b}` (or a general factor reference) under the D9 dependency rules. The document says "the corresponding transformer factor" and does not spell out primary / secondary; the regression assumes that ratio.
- **Proposed regression:** 3530 = 0x08FC (2300), 14-15 = 0x469C 0x4000 (f32 20000.0), 16-17 = 0x42C8 0x0000 (f32 100.0) -> 2300 x 0.1 x 20000 / 100 = 46000 V.

### `c02-schneider-4q-pf`: The four-quadrant float power factor needs a piecewise decode that the draft's linear conversion cannot express.

- **Class 2, vendor:** Schneider Electric (PM5560)
- **Owner:** maintainer
- **Decision:** D6
- **Evidence:** PM556x workbook 'Data Types'!A15 "4Q FP PF" (B15 "Four Quadrant Floating Point Power Factor", C15 "-2 - 2", D15 N/A 0xFFC00000, E15 pseudo code). Used by 'Register List' row 230 Power Factor Total, register 3084, 2 registers, 4Q_FP_PF; also rows 234 (3092), 4904 (27312), 4993 (27788).
- **Detail:** E15: if reg > 1 then PF = 2 - reg, leading; if reg < -1 then PF = -2 - reg, leading; if \|reg\| = 1 then unity; otherwise PF = reg, lagging. §6.4 is one linear formula and §11 reserves conditional conversion (`when`). The same workbook offers plain float PF registers (3192 "Power Factor Total IEC", -1 to 1), so a contract can avoid the encoding, but the 4Q registers (including min/max) cannot be decoded. The INT16U "IEC" and "Lead Lag" PF registers (3196, 3197: "if a negative value is reported, add 32768 then divide by 1000" for lagging) are expressible as a 0x7FFF mask with exponent10 -3 plus a bit-15 flag point.
- **Proposed regression:** f32 0x3F99 0x999A (1.2) -> 0.8, leading; f32 0xBFE6 0x6666 (-1.8) -> -0.2, leading; f32 0xBF4C 0xCCCD (-0.8) -> -0.8, lagging; f32 0x3F80 0x0000 (1.0) -> 1.0, unity (once the word order is known).

### `c03-reactive-power-unit`: UCUM has no var, so reactive power carries no machine-readable unit.

- **Class 3, vendor:** Solis (S6-GR1P4K, S6-GR1P5K, S6-GR1P6K)
- **Owner:** maintainer
- **Decision:** D13
- **Evidence:** Solis Ver3.7 page 9, 'Reactive power value', 3055-3056, S32, unit '1Var'. Also Fronius VAr 40090 (unit 'VAr', not mapped).
- **Detail:** The contract omits unit and writes 'Vendor unit: Var.' in description; W001 then warns. Options: allow an annotated UCUM unit such as 'W{reactive}' or a small non-UCUM list (var, varh) alongside UCUM.
- **Proposed regression:** input registers 3055-3056 = [0x0000, 0x03E8] -> 1000 with unit var (today: 1000, no unit)

### `c05-tecsystem-disabled-channel-zero`: A disabled channel reads temperature 0000 (0 degC); validity depends on a bit in another register.

- **Class 5, vendor:** TECSYSTEM (NT935 AD, NT935 ETH, T1048 with Modbus)
- **Owner:** maintainer
- **Decision:** D9
- **Evidence:** NT935 AD p. 20 notes for remote programming: "If the channel 4 is not enabled ... 1. Measured temperatures = 0000 (0°C) ... 4. Channel setting = %xxxxxxx0"; the enable bit is CAN_enabled, bit 0 of "Ch4 Setting" (address 60, CHn SETTING note p. 26); the value is "Ch4 temper." at address 37. T1048 p. 20 applies the same rule to every channel (Ch1..Ch4 temper. 25/29/33/37, settings 57..60).
- **Detail:** 0x0000 is also a legitimate 0 degC reading on an enabled channel, so listing it in `invalid` would discard real data, and the draft cannot make validity conditional on another point's bit (6.6 only knows raw sentinels, non-finite floats and failed dependencies). Spec 11 reserves "conditional conversion and availability (when)"; this is a concrete corpus case for it. The contracts only say it in the description.
- **Proposed regression:** ch4_setting (HR 60) = 0x0000, ch4_temperature (HR 37) = 0x0000 -> expected ch4_temperature invalid; the draft yields 0 Cel good. With ch4_setting = 0x0001 and the same raw value -> 0 Cel good.

### `c07-enum-selected-scale-unit`: The scale and unit of a temperature register are selected by enum configuration registers, which 0.1 cannot express.

- **Class 7, vendor:** AutomationDirect (SIO-MB08THMS)
- **Owner:** maintainer
- **Decision:** D9 (dependencies), with D6 (numeric model) and D13 (units)
- **Evidence:** SIO-MB08THMS guide PDF p. 5: 40041-40048 ANALOG INPUT #n VALUE, i16, "Values for thermocouple sensor types are stored with one implied decimal place. Values are stored with two implied decimal places for mV inputs" (examples 246 -> 24.6 °C, 24656 -> 246.56 mV); Input Type 40031 (low byte channel 0, codes 1 = 250mV, 4-11 = TC J..N; PDF p. 4); Degree Units 41218 (0 Celsius, 1 Fahrenheit, 2 Kelvin; PDF p. 6). Same pattern without a stated formula: Moxa E1240 AI_mode 40025 selects the range of AI_rawValue 30001.
- **Detail:** Checked: exponent10 point references (6.4) need a register holding the exponent itself, not a type code; enum (6.5) only names values; variants (5.6) are firmware/hardware, not runtime configuration; masks (6.3) and repeats (5.3) do not apply. Section 11 reserves conditional conversion ("when"). The contract fixes exponent10 -1 and unit Cel and states the condition in info.description.
- **Proposed regression:** Input Type 40031 = 0x0505, Degree Units 41218 = 0x0000, 40041 = 0x00F6 -> ai_0 = 24.6 Cel. Input Type 40031 = 0x0501, 41218 = 0x0000, 40041 = 0x6050 -> ai_0 = 246.56 mV. Input Type 40031 = 0x0505, 41218 = 0x0001, 40041 = 0x00F6 -> ai_0 = 24.6 [degF].

### `c07-validity-from-status-register`: A channel value's validity is flagged in a separate status register (or depends on a mode), which `invalid` sentinels cannot express.

- **Class 7, vendor:** AutomationDirect (SIO-MB08THMS, ioLogik E1240)
- **Owner:** maintainer
- **Decision:** D9 (dependencies; failure => invalid)
- **Evidence:** SIO-MB08THMS PDF p. 5: 40050 BREAK STATUS, bit n set "When a break condition is detected (e.g., broken sensor, disconnected cable, or over temperature)" for channel n, whose value is at 40041 + n. Moxa E1200 manual PDF p. 106 AI_status 30061+n (1 burnout, 2 over range, 3 under range) and section 3 p. 3-14: in 4-20 mA burnout mode raw 0000h means burnout and FFFFh over range, while 0000h is a valid raw value in the 0-10 V and 0-20 mA modes.
- **Detail:** Checked: 6.6 `invalid` lists raw sentinels of the point itself, so a status bit in another register cannot invalidate it, and a sentinel that applies in one AI_mode only cannot be scoped. Section 11 reserves conditional availability ("when"). The contracts expose the status register as flags/enum and do not mark sentinels.
- **Proposed regression:** 40050 = 0x0001, 40041 = 0x0000 -> ai_0 invalid; 40050 = 0x0000, 40041 = 0x00F6 -> ai_0 = 24.6 Cel. E1240: 40025 = 4 (4-20 mA burnout), 30001 = 0x0000 -> ai_raw_value[0] invalid; 40025 = 0 (0-10 V), 30001 = 0x0000 -> 0.

### `c08-abb-ratio-scaling`: Fieldbus actual values scale to another parameter (20000 = a speed or frequency parameter value).

- **Class 8, vendor:** ABB (ACS580, ACH580, ACS880)
- **Owner:** maintainer
- **Decision:** D6, D9
- **Evidence:** FSCA-01 pp. 66-67: Act1 is scaled so that 20000 corresponds to REFx MAX, the drive's speed scaling parameter (ACS880 46.01). Vendor address 400005 (Classic profile, p. 35).
- **Detail:** The draft can express a percentage (multiplier 0.005 gives % of the scaling parameter), and exponent10 can reference a point, but no conversion can take a multiplier from another point's value. Engineering units need value = raw x ref / 20000.
- **Proposed regression:** Act1 raw 10000 with 46.01 = 1500 rpm -> 750 /min.

### `c08-schneider-energy-decades`: Input energy is one value split over five registers in base 1000.

- **Class 8, vendor:** Schneider Electric (ATV340, ATV630)
- **Owner:** maintainer
- **Decision:** D6, D7
- **Evidence:** NVE61728 Parameters rows 942-946 and EAV64332 rows 834-838: IC0 (Wh) to IC4 (TWh) at 16#2982 = 10626 to 16#2986 = 10630, each 0 ... 999.
- **Detail:** The draft can only give five separate points; no type or conversion combines registers with a base-1000 radix (similar to the MOD10K case in the brief).
- **Proposed regression:** registers [123, 456, 7, 0, 0] at 10626-10630 -> 7456123 W.h.

### `c08-schneider-cmi-frequency-unit`: A control-word bit selects the output frequency scale, one option relative to another parameter.

- **Class 8, vendor:** Schneider Electric (ATV320, ATV340, ATV630)
- **Owner:** maintainer
- **Decision:** D6, D9
- **Evidence:** Registers sheet, CMI bit 9 (ATV320 Registers!C13:D16): "output frequency (rFr) unit", "= 0: 0.1 Hz", otherwise "32767 corresponds to [Max frequency] (tFr)". RFR at 16#0C82 = 3202.
- **Detail:** Contracts assume bit 9 = 0. The draft has no variant selected by a register bit for a conversion, and no ratio to another point (see c08-abb-ratio-scaling).
- **Proposed regression:** CMI bit 9 = 1, tFr = 60.0 Hz, RFR raw 32767 -> 60.0 Hz; raw 16384 -> 60.0 x 16384 / 32767 Hz.

### `c09-kohler-unit-system-register`: A readable register (400139 Metric Units) switches the unit of other registers between metric and English.

- **Class 9, vendor:** Kohler (Decision-Maker 550)
- **Owner:** maintainer
- **Decision:** D9
- **Evidence:** TP-6113 12/21 p.15: "The controller display setting determines whether the units are returned or interpreted as metric or English. Read or alter this setting in register 40139 (550 controller only)." p.46: "400139 Metric Units RW WORD 1 = True, 0 = False". p.43: "400033 Oil Pressure* RO WORD kPa/psi", "400034 Coolant Temperature* RO SWORD Degrees C/Degrees F".
- **Detail:** A point has one static unit and conversion (6.4); variants (5.6) select firmware/hardware subsets, not a runtime register value; section 11 reserves conditional conversion (`when`). The contract could only pick one setting or drop the unit. Related: c08-schneider-cmi-frequency-unit (control bit selects the scale) and c10-config-selected-unit (setting not readable over Modbus); this case is readable, so a runtime could follow it.
- **Proposed regression:** 400139 = 0x0001, 400034 = 0x0055 -> 85 Cel; 400139 = 0x0000, 400034 = 0x00B9 -> 185 [degF]. Register numbers as in the document; PDU addresses pending c09-kohler-address-base.

### `c10-negated-scale-factor`: A scale-factor register that divides by 10^SF cannot be expressed; exponent10 references only multiply.

- **Class 10, vendor:** Kipp & Zonen (SMP3, SMP6, SMP10)
- **Owner:** maintainer
- **Decision:** D9 (D6)
- **Evidence:** Smart Pyranometer Modbus Communication Manual 0426210, p5, IO_SCALE_FACTOR (PDU address 4, S16): "2 floating point result = integer register X / 100; 1 ... / 10; 0 ... X; -1 ... X * 10", applying to IO_SENSOR1_DATA (5), IO_RAW_SENSOR1_DATA (6), IO_SENSOR2_DATA (10), IO_RAW_SENSOR2_DATA (11).
- **Detail:** exponent10: {point: scale_factor} computes raw × 10^SF, the inverse of the vendor rule. E007 forbids a conversion on the referenced point, so multiplier -1 cannot negate it, and the factor is dynamic (IO_AUTO_RANGE), so variants do not help. The contracts carry the irradiance unconverted and unitless with the rule in the description. Options for the maintainer: a sign on the reference (for example exponent10: {point: scale_factor, negate: true}) or allowing an integer multiplier of -1 on the referenced point.
- **Proposed regression:** input registers 4 = 0x0002, 5 = 0x3039 -> irradiance 123.45 W/m2; 4 = 0xFFFF, 5 = 0x0064 -> 1000 W/m2 (the current draft with exponent10 {point} would give 1234500 and 10).

## Questions on the draft

### `c01-msw-overflow-sentinel`: Overflow is signalled by the most significant word alone (MSW == 7FFFh); invalid lists exact raw values only, so this needs 65536 entries.

- **Class 1, vendor:** Carlo Gavazzi (EM530, EM540)
- **Owner:** maintainer
- **Decision:** D6 (numeric model; section 6.6 validity)
- **Evidence:** EM530/EM540 v1.3 p.10 section 3.3: 'The overflow indication EEE is displayed when the MSW value of the relevant variable is 7FFFh.' Applies e.g. to V L1-N 0120h (300289) INT32, LSW first.
- **Detail:** For an i32 this is 65536 raw values (0x7FFF0000-0x7FFFFFFF): expressible only as a 65536-entry invalid list. A masked u16 shadow point over the MSW would overlap the i32 (E002) and cannot drive its quality. Contracts here carry no invalid list for EM530/EM540. Option: invalid entries as {mask, value} or a range. Recorded as a question because the draft can express it literally.
- **Proposed regression:** FC04 0x0120 count 2 -> [0x0000, 0x7FFF] (LSW first) -> raw 0x7FFF0000 -> quality invalid (today decodes as 214741606.4 V).

### `c01-var-unit`: UCUM has no var; the draft allows it with warning W006, the corpus builder rejects it, so reactive points carry no unit.

- **Class 1, vendor:** ABB; Carlo Gavazzi; Eastron (B21, B23, B24, EM511, EM530, EM540, SDM230, SDM630)
- **Owner:** maintainer
- **Decision:** D13 (semantics and units)
- **Evidence:** ABB B21 p.73 5B1C 'Reactive power Total ... var'; EM511 p.13 0008h 'var*10'; SDM230 p.2 30025 'VAr'.
- **Detail:** Contracts here omit the unit (W001) and put the vendor unit in description, because corpus/run.py rejects var. Decide: accept var under W006, prescribe a UCUM spelling (e.g. V.A{reactive}), or keep omitting it.
- **Proposed regression:** ABB 0x5B1C i32 raw 12345, exponent10 -2 -> 123.45 with a machine-readable reactive-power unit.

### `c01-float-coded-enum`: Settings are enumerations transported as IEEE floats; may enum apply to an f32 whose value is integral?

- **Class 1, vendor:** Eastron (SDM230, SDM630)
- **Owner:** maintainer
- **Decision:** D6 (numeric model; section 6.5)
- **Evidence:** SDM630 v1.8 p.7 40029 Network Baud Rate '0 = 2400 baud ... 4 = 38400 baud', 'Data Format : Float'; SDM230 p.4 40029 and 40087 Pulse1 Energy Type, same pattern.
- **Detail:** Section 6.5 says enumerations map raw integers; E013 only defines ranges for integer types. Not mapped.
- **Proposed regression:** FC03 0x001C count 2 -> [0x4000, 0x0000] (f32 2.0) -> enum 9600 baud.

### `c01-u64-sentinel-precision`: invalid: [18446744073709551615] on u64 points exceeds 2^53; JSON consumers parsing contracts as binary64 cannot match it.

- **Class 1, vendor:** ABB (B21, B23, B24)
- **Owner:** maintainer
- **Decision:** D6 (numeric model)
- **Evidence:** ABB B21 p.69 'Unused registers': unsigned quantities read FFFF in all registers; 5000 Active import kWh is 4 registers Unsigned (p.70).
- **Detail:** Section 6.4 requires raws above 2^53 to stay exact and be carried as strings in interchange, but schema $defs/point.invalid only allows integers.
- **Proposed regression:** FC03 0x5000 count 4 -> [0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF] -> active_import_energy invalid in every implementation, including those reading the contract with a binary64 JSON parser.

### `c01-odd-length-string`: 13-character serial number in 7 registers with the last low byte 'not to be used'.

- **Class 1, vendor:** Carlo Gavazzi (EM511, EM530, EM540)
- **Owner:** maintainer
- **Decision:** D6 (section 6.2 strings)
- **Evidence:** EM511 p.21 / EM530-EM540 p.30 section 4.10: 5000h-5006h letters 1-13, 5006h 'LSB: not to be used'.
- **Detail:** A string point decodes 14 bytes and stops only at NUL; if the unused byte is not NUL or space the value gains a stray character. Not mapped.
- **Proposed regression:** FC04 0x5000 count 7 with the 14th byte 0x41 -> serial_number of 13 characters, without the trailing 'A'.

### `c01-configurable-word-order`: Float word order is a runtime setting (Register Order); contracts assume the default.

- **Class 1, vendor:** Eastron (SDM230, SDM630)
- **Owner:** maintainer
- **Decision:** D5 (byte/word order); D3 (scope)
- **Evidence:** SDM630 v1.8 p.1 'Most significant register first (Default) ... See Holding Register Register Order'; p.7 writing 2141.0 sets the order for all float transactions.
- **Detail:** Variants (5.6) could duplicate every point per order, but they model firmware/hardware, not configuration. Same pattern: SDM630 wiring system decides which values read zero (p.2). Decide whether configuration-dependent semantics belong in variants, a conditions profile, or stay out of scope.
- **Proposed regression:** Register Order reversed: FC04 0x0000 count 2 -> [0x8000, 0x4370] -> voltage_l1_n 240.5 V.

### `c01-safe-gap-over-points`: A safe_gap range that covers defined points as well as holes.

- **Class 1, vendor:** ABB (B21, B23, B24)
- **Owner:** maintainer
- **Decision:** D10 (read constraints)
- **Evidence:** ABB B21 p.69 / B23-B24 p.85: 'Reading any registers within this range [1000-8EFF] will result in a normal Modbus response'.
- **Detail:** Mapped as one safe_gap range 0x1000 count 0x7F00. Section 7 says 'undefined but safe'; confirm a validator accepts points inside a safe_gap range.

### `c02-janitza-rotation-float-enum`: The rotation field is a float carrying the codes 1, 0 and -1; §6.5 enums map raw integers only.

- **Class 2, vendor:** Janitza electronics (UMG 96RM, UMG 96RM-E, UMG 96RM-PN)
- **Owner:** maintainer
- **Decision:** D6
- **Evidence:** DE PDF p.17, 19052 FLOAT RD "Rotation field; 1=right, 0=none, -1=left" (also 938 on PDF p.19); EN PDF p.19, 19052.
- **Detail:** Left out. Decide whether an enum may apply to an f32 whose values are exact integers, or whether such points stay plain numbers with the codes in the description.

### `c02-schneider-mod10k`: Could not confirm whether any PM5000 register uses an INT64 MOD10K energy format.

- **Class 2, vendor:** Schneider Electric (PM5110, PM5330, PM5560)
- **Owner:** maintainer
- **Decision:** D6
- **Evidence:** PM556x 'Data Types' sheet lists INT64 (row 7) and no MOD10K type; energy at 3204 is INT64 Wh. The legacy .xls was only byte-scanned (strings): "INT64", "INT64U" and "4Q FP PF" occur, "MOD10" does not.
- **Detail:** Recheck once the .xls can be read (c02-schneider-xls-reader).

### `c03-fronius-sunspec-discovery`: Vendor says SunSpec register addresses are not constant and models should be located by scanning.

- **Class 3, vendor:** Fronius (Primo 3.0-1, Primo 4.0-1, Primo 5.0-1)
- **Owner:** maintainer
- **Decision:** D12
- **Evidence:** Datamanager manual 'Register addresses': 'Register addresses do not remain constant ... Search for the model ... Then work with offsets'; 'Changing the Data Type': model type changes the addresses of all subsequent models.
- **Detail:** Contract keeps the vendor's fixed Complete Map addresses for the Common block and inverter model only, which are first and follow a fixed-length block (checked). Later models (120-124, 160) were not mapped. Confirm this is acceptable before the sunspec profile exists.

### `c03-config-dependent-layout`: Layout depends on a configuration register (F_ModelType) and Solis scope on production date; variants.match has only firmware/hardware.

- **Class 3, vendor:** Fronius (Primo 3.0-1, Primo 4.0-1, Primo 5.0-1)
- **Owner:** maintainer
- **Decision:** D3
- **Evidence:** Fronius Register sheet row 6: F_ModelType 216, '1: Floating point 2: Integer & SF' selects model 111 vs 101 at 40070; Solis protocol section 3 item 1: 'applies to machines manufactured after mid-2023'.
- **Detail:** Today the contracts say this in info.description. A variant without match could carry it as text. Should variant match allow a register condition (e.g. sunspec_model_type == 2) or a production date?

### `c03-solis-composite-status`: Inverter status 3043 is subdivided by register 3029; the draft cannot express the combined meaning.

- **Class 3, vendor:** Solis (S6-GR1P4K, S6-GR1P5K, S6-GR1P6K)
- **Owner:** maintainer
- **Decision:** D12
- **Evidence:** Appendix 2 'M3043 and M3029' page 18: 0003H(0000H) Generating, 0003H(xx01H) LimByTemp, 0003H(xx02H) LimByFreq, ...; 0000H(0001H) Grid Off.
- **Detail:** Each register can be an enum or flags on its own; the combination is conditional interpretation, which section 11 reserves (conditions profile). Not mapped. Regression if pursued: 3043=0x0003, 3029=0x0001 -> generating, limited by temperature.

### `c03-string-not-available`: A not-available string is all zero registers; invalid only takes integers.

- **Class 3, vendor:** Fronius (Primo 3.0-1, Primo 4.0-1, Primo 5.0-1)
- **Owner:** maintainer
- **Decision:** D6
- **Evidence:** Datamanager manual 'Unavailable data records': 'stringX: all X registers filled with 0x0000'.
- **Detail:** Section 6.2 decodes this to an empty string, so quality stays good. Is an empty string enough, or should strings get a validity rule?

### `c03-sma-sunspec-discovery`: SMA's SunSpec document gives no addresses; points can only be located by SunSpec model discovery.

- **Class 3, vendor:** SMA (SB3.0-1AV-41, SB5.0-1AV-41, STP5.0-3AV-40)
- **Owner:** maintainer
- **Decision:** D12
- **Evidence:** SunSpecModbus-TI-en-11 page 7: 'All information models start with an ID register and a length register. This information is used to cycle through or scan the information models'; models are excluded dynamically; blocks repeat per DC input.
- **Detail:** Needs the sunspec profile with runtime discovery (D12), or a fixed-address SMA register list as an alternative source. Fixed SunSpec addresses must not be invented from the models release.

### `c04-fronius-dynamic-model-chain`: Absolute addresses are only valid for one configuration of the SunSpec model chain.

- **Class 4, vendor:** Fronius (Symo GEN24 6.0 Plus, Symo GEN24 8.0 Plus, Symo GEN24 10.0 Plus)
- **Owner:** maintainer
- **Decision:** D12
- **Evidence:** Manual, Register addresses: "Register addresses do not remain constant. The actual register addresses depend on the composition of the dynamic SunSpec register list." The ZIP ships separate maps for int+SF vs float and storage vs no storage; the storage model 124 starts at address 40343 (int+SF) or 40353 (float).
- **Detail:** The contracts state the condition in info.description only. The draft cannot say "valid when register 40343 reads 124" or select a map by a device setting; variants match firmware/hardware only (5.6). The planned sunspec profile (section 10, model-chain discovery) would cover it.
- **Proposed regression:** Address 40343 = 124 (0x007C), 40344 = 24 -> storage block applies, ChaState read at 40351; address 40343 = 0xFFFF (end block, no battery configured) -> storage points not applicable rather than decoded.

### `c04-fronius-scale-factor-coherence`: Auto-scaled scale factors change at runtime; a value and its _SF read in two requests can mismatch.

- **Class 4, vendor:** Fronius (Symo GEN24 6.0 Plus, Symo GEN24 8.0 Plus, Symo GEN24 10.0 Plus)
- **Owner:** maintainer
- **Decision:** D9
- **Evidence:** Manual, Scale factors: "Scale factors ... are not static ... also change with the runtime (auto-scale)". Complete Map W_SF (40085) "auto-scaled on W"; DCA_SF/DCV_SF/DCW_SF (40256-40258) "auto-scaled on DCA 1-N".
- **Detail:** The contracts leave stability at the default (dynamic), so W005 will warn. The draft does not say that a value and its exponent10 point must come from the same request, and blocks.coherent needs a vendor guarantee. Decide whether D9 should require reading value and scale factor in one request when the factor is dynamic.

### `c04-schneider-device-present-gate`: A device-level "data valid" register invalidates all other points, which the draft cannot express.

- **Class 4, vendor:** Schneider Electric (Conext SW 2524 230, Conext SW 4024 230)
- **Owner:** maintainer
- **Decision:** D9
- **Evidence:** 503-0244-01-01 page 3, 0x0041 Device Present uint16 "0=Inactive (all data invalid) 1=Active (data valid)".
- **Detail:** Draft 6.6 marks a value invalid only through its own `invalid` list, non-finite floats or a failed exponent10/verifyWith dependency. Conditional availability (`when`) is reserved (section 11, `conditions` profile), so this is recorded as a question rather than as a gap.
- **Proposed regression:** Address 65 (device_present) = 0 and address 84 (battery_temperature) = 0x7440 -> battery_temperature quality invalid (today: 29760 x 10^-2 - 273 = 24.6 Cel, good); address 65 = 1 -> 24.6 Cel, good.

### `c04-victron-gateway-unit-id`: Gateway-assigned unit IDs do not fit unitId.mode fixed/configurable/ignored.

- **Class 4, vendor:** Victron Energy (MultiPlus-II, Quattro, EasySolar-II GX)
- **Owner:** maintainer
- **Decision:** D3
- **Evidence:** Register list sheet Unit ID mapping row 2: "since Venus version 2.60, Unit Ids are assigned dynamically"; row 4: unit ID generally equals the device instance.
- **Detail:** The contracts carry unitId.notes without a mode. Decide whether 0.1 needs a mode such as `assigned` (by a gateway) or whether this stays deployment configuration under D3.

### `c05-comem-event-timestamp`: Event time is Timestamp Hi + 2^16 x Timestamp Low seconds since 2014-01-01, with inverted register names.

- **Class 5, vendor:** COMEM (CU eOLI)
- **Owner:** vendor
- **Decision:** D6
- **Evidence:** CU eOLI manual p. 34 Table 4, 0x2301 "Timestamp Hi [Event 1]" and 0x2302 "Timestamp Low [Event 1]" (repeating to 0x248E): "Event Date/Time = Timestamp Hi (seconds) + (2^16) x Timestamp Low (seconds) + (01-Jan-2014 00hh:00min:00sec)".
- **Detail:** Read literally, the register named "Hi" is the low word (a u32 with wordOrder little). The draft can decode the seconds count, but it has no timestamp type or epoch (spec 11 reserves timestamp types), and no time zone is stated. Not a spec-gap yet because the source is not admitted and the names contradict the formula; revisit if COMEM documents the encoding.
- **Proposed regression:** 0x2301 = 0x0001, 0x2302 = 0x0002 -> 131073 s after 2014-01-01T00:00:00 = 2014-01-02T12:24:33 (time zone unstated).

### `c05-tapcon-230-avt-counter-words`: Operation Counter LSW/MSW rows each give the range 0..99999999.

- **Class 5, vendor:** Maschinenfabrik Reinhausen (TAPCON 230 AVT)
- **Owner:** maintainer
- **Decision:** D5
- **Evidence:** Table 8 (p. 19), input registers 3 and 4, "The value of Operation Counter consists of LSW and MSW".
- **Detail:** Mapped as one u32, least significant word at register 3 (wordOrder little). The per-row range is the combined counter range; confirm that the words are binary halves and not a decimal split.

### `c05-tecsystem-address-base`: Addresses are taken as PDU addresses from the "Address LO (10)" column header.

- **Class 5, vendor:** TECSYSTEM (NT935 AD, NT935 ETH, T1048 with Modbus)
- **Owner:** maintainer
- **Decision:** D4
- **Evidence:** NT935 AD p. 20 FC 3 request "Starting address HI, Starting address LO"; mapping table header "Address LO (10)" / "Data HI" / "Data LO" (pp. 22-25). The table starts at 1 (model string).
- **Detail:** The header names the request's Starting address LO byte in decimal, so the base is stated, but there is no worked example. Confirm on a device: reading PDU address 3 must return 0x20 (space) in the high byte followed by the first firmware digit; with a one-based reading it would return model digits.
- **Proposed regression:** FC 03, start 3, count 1 -> high byte 0x20.

### `c05-mht410-saturation-codes`: 7FFFhex means "32767 or larger" and 8001hex "-32767 or smaller"; the draft has no saturated state.

- **Class 5, vendor:** Vaisala (MHT410)
- **Owner:** maintainer
- **Decision:** D6
- **Evidence:** Table 60 (p. 111), applied to the 16-bit integer registers 257..270 (Table 62, p. 113).
- **Detail:** The contract marks 0x8000 (not available) as invalid and puts the saturation meaning in the descriptions. A runtime will report raw 0x7FFF as a good 3276.7 degC. Decide whether 6.6 needs a quality beyond good/invalid (for example a clipped flag), or whether sentinels that mean "out of range" should simply be invalid.
- **Proposed regression:** oil_temperature_int raw 0x7FFF -> draft 3276.7 Cel good; vendor meaning ">= 3276.7 Cel".

### `c05-mmt162-power-up-delay`: The guide says to wait five seconds after power-up before sending Modbus requests.

- **Class 5, vendor:** Vaisala (MMT162)
- **Owner:** maintainer
- **Decision:** D10
- **Evidence:** Appendix A, Supported Modbus Functions note (PDF p. 73).
- **Detail:** `constraints` has minRequestIntervalMs but nothing for a start-up delay; the contract keeps it in info.description. Decide whether D10 should cover start-up timing or leave it to documentation.

### `c05-test-value-registers`: Vendor test registers with known constants could anchor level-4 device tests.

- **Class 5, vendor:** Vaisala (OPT100, MHT410)
- **Owner:** maintainer
- **Decision:** D14
- **Evidence:** OPT100 Table 36 (pp. 139-140), e.g. 0x00C9 u32 = 1234567890; MHT410 B.3.1 recommends reading a test value register.
- **Detail:** The OPT100 contract includes test_value_u32 with stability constant and the constant in the description. A machine-readable "expected constant" key would let device tests check word order automatically; decide whether that belongs in the contract or in the test vectors.

### `c06-configured-default-scaling`: Scale factors are defaults that the device configuration can change and that no register reports.

- **Class 6, vendor:** Siemens (7SJ80, 7SK80, 7RW80, REF615, REM615, RET615)
- **Owner:** maintainer
- **Decision:** D9
- **Evidence:** Siemens bus mapping pdf page 27 (chapter 1.5): "The given default scaling values ... apply to installations with ... Full Scale Voltage (parameter address 1101) ... Full Scale Current (parameter address 1102)" and "Changes of the scaling of the measured values are possible". ABB point lists: "Scale Scale factor, default setting" (REF615 pdf page 17), "Scale factor as default" (RET615 table 110, pdf page 71); the 615 series protocol manuals (1MRS756468 and 1MAC057386-MB, 3.4.2): "The measurands can be freely rescaled by the user", and 3.4.5 "The user can freely configure these parameters with Communication Management tool in PCM600".
- **Detail:** The contracts carry the default exponent10 and say in the description that it is a default. The draft cannot mark a conversion as "default, configurable outside Modbus": exponent10 references (§6.4) need a readable point, and stability (D9) covers only referenced factors. Should a contract be able to say that its conversion is a configuration default (for example a conversion-level stability or provenance flag), or is that deployment configuration and out of scope (D3)?

### `c06-siemens-data-invalid-flag`: The validity of every value depends on bit 15 "Data invalid" of the diagnostics register 40129.

- **Class 6, vendor:** Siemens (7SJ80, 7SK80, 7RW80)
- **Owner:** maintainer
- **Decision:** D9
- **Evidence:** Bus mapping chapter 1.6.3 Diagnostics (pdf page 31), row 40129/2^15 "Data invalid": set by the Modbus slave when the data in the message are invalid.
- **Detail:** `invalid` (§6.6) names raw sentinel values of the point itself. Validity that depends on a flag in another register is conditional availability, which §11 reserves. The contracts map the flag and describe it. Is a point-to-point validity link (point X is invalid while flag F of point D is set) in scope for 0.x?

### `c06-flags-with-bit-field`: The Sepam check-word mixes a 4-bit field (mapping number, bits 3-0) with flags (bits 4-15); the draft cannot express both cleanly.

- **Class 6, vendor:** Schneider Electric (Sepam S20, Sepam T20, Sepam M20)
- **Owner:** maintainer
- **Decision:** D14
- **Evidence:** Format X: Sepam check-word, pdf page 111: "bit 3-0 mapping number (1 to 16)" (later "from 1 to 15"), bits 4 and 6-15 named. Spec §6.5 says flags name bits "or bit ranges via `width`", but schema/0.1/contract.schema.json flagSetDef has only bit, name, label, description.
- **Detail:** Two options: a full-register flags point plus a mask point 0x000F, which the overlap rule rejects; or masked flags with mask 0xFFF0, where it is unclear whether flag bits count from the raw register or from the shifted value (§6.3 shifts). The contract maps the flags on the whole word and leaves out the mapping number. Questions: are flag bit numbers relative to the masked value, and should flags `width` be in the schema (the spec and schema disagree)?

### `c06-measurement-saturation`: Sepam and the ABB 615 series clamp over-range measurements to the format maximum; the draft has no "saturated" quality.

- **Class 6, vendor:** Schneider Electric (Sepam S20, Sepam T20, Sepam M20, REF615, REM615, RET615)
- **Owner:** maintainer
- **Decision:** D6
- **Evidence:** Data encoding, pdf page 111: "If a measurement overruns the maximum permissible value for the related format, the value read for the measurement will be the maximum permissible value for the format." ABB 1MRS756468 table 11: "If the Modbus value exceeds the register size limit after the scaling, then it saturates at the register max value", and 3.4.8.7 "the register value always saturates at the min. and max. values for the register type in question. The value does not roll over." Unavailable ABB points "always return value 0" (REF615 pdf page 17).
- **Detail:** 0xFFFF (16 NS) is a valid but clamped reading, not an `invalid` sentinel (§6.6). Should §6.6 offer an over-range or clamped quality? Zero-for-unavailable cannot be a sentinel either, because 0 is a legal value.

### `c06-time-tagged-records`: Every relay delivers time-tagged events and fault records through handshake structures that read-only flat points cannot express.

- **Class 6, vendor:** Schneider Electric (Sepam S20, Sepam T20, Sepam M20, SIL-A, SIA-C, SIA-B Specific CT, REF615, REM615, RET615, 7SJ80, 7SK80, 7RW80)
- **Owner:** maintainer
- **Decision:** D3
- **Evidence:** Sepam: event zones 0040-0060 and 0070-0090 with an exchange word written by functions 6/16 (pdf page 112), and TS transitions time-tagged (pdf page 116). Fanox SIL-A general memory map (pdf page 7): "Read the oldest Event 400 11 EVENTO2", "Read a complete fault report 8400 54 EVENTO2", with FH = Year(UINT).month(UCHAR).day(UCHAR)... in 5 registers. ABB REF615: "Time structure" registers 2004-2006 (pdf page 20). RET615: event record structure from 9250 with a written read selection (table 121) and timestamped demand values (tables 139, 141). Siemens 1.6.7 event recorder 40601-40626 and "Absolute time" in the profile manual.
- **Detail:** Timestamps and BCD/packed time are reserved (§11), and reading these structures needs writes (D3, D11). The packed FH fields could be split into byte masks (§6.3), but no type yields one timestamp. Record this as input for a later events/timestamps profile. Not a strict spec-gap, because §11 already reserves it.

### `c06-per-unit-quantities`: Currents and voltages are given in multiples of the rated values (xIn, xUn); UCUM has no unit for that.

- **Class 6, vendor:** ABB (REF615, REM615, RET615)
- **Owner:** maintainer
- **Decision:** D13
- **Evidence:** REF615 point list rows 138-141 "0...40.00 [xIn]" and 152 "0...4.00 [xUn]" (pdf page 19); RET615 rows 138-140, 152-154 and 2080-2082 "[xIn]" (tables 140, 142, 156). Protocol manual 3.4.5.2: "The internal representation of the per-unit values is always 1.0 at nominal current or voltage"; the primary-value option ([A], [kV]) is a configuration setting that no register reports.
- **Detail:** The RET615 contract leaves the unit out and says "in multiples of the rated current In"; the REF615 and REM615 measurands are no longer mapped (c06-abb-default-offset), but their rows have the same notation. Should the draft offer a per-unit convention (unit "1" plus a semantic reference to the nominal), or is this for the semantics layer (D13)?

### `c07-count-array-index`: Should point `count` arrays carry an index base or element names, as group repeats do?

- **Class 7, vendor:** Moxa (ioLogik E1210, ioLogik E1212, ioLogik E1240, ET-2251, ET-2268)
- **Owner:** maintainer
- **Decision:** D7 (structure)
- **Evidence:** Moxa Appendix A rows have a Length per channel group (e.g. DI_status 10001, Length 16) and ICP DAS section 6.3 rows "1 to nDI"; the contracts use `count`, which cannot name the channel that element 0 belongs to (Moxa names channels from 00, e.g. "DI-all_statusFromDI-00").
- **Detail:** Group repeats have indexBase (5.3) but corpus contracts must be flat; consider an indexBase on `count` points.

### `c08-schneider-current-decade`: An enum register selects a power-of-ten scale through non-exponent codes.

- **Class 8, vendor:** Schneider Electric (ATV340, ATV630)
- **Owner:** maintainer
- **Decision:** D9
- **Evidence:** EAV64332 Parameters rows 846-851 (INRC at 16#2649 = 9801) and Enumerations rows 264-268: 20 -> 0.001, 30 -> 0.01, 40 -> 0.1, 50 -> 1, 60 -> 10.
- **Detail:** Expressible only by an affine trick (exponent = 0.1 x code - 5 via conversion on the selector point, then exponent10 {point}) if conversion applies before the reference. The workbook does not tie LCR to INRC, so nothing is mapped.

### `c08-flags-width`: Spec section 6.5 mentions a flag width, but the schema's flagSetDef has no width property.

- **Class 8, vendor:** AutomationDirect (GS20, GS30, GS4)
- **Owner:** maintainer
- **Decision:** D7
- **Evidence:** spec/openmodbus-0.1-draft.md 6.5 versus schema/0.1/contract.schema.json $defs.flagSetDef. GS20 p. 297 2101h bits 1-0 and 4-3 are multi-bit fields.
- **Detail:** The multi-bit fields were mapped as separate points with mask and enum; align spec and schema.

### `c09-kohler-dm3500-sentinel-ranges`: "Data unknown" is a range of 32 raw values (0x7FE0-0x7FFF signed, 0xFFE0-0xFFFF unsigned).

- **Class 9, vendor:** Kohler (Decision-Maker 3500)
- **Owner:** maintainer
- **Decision:** 6.6 (proposed, no D-number; closest D6)
- **Evidence:** TP-6113 12/21 p.105: "0x7FE0 - 0x7FFF INT 32736 - 32767 ... The register is supported, but the data in the register is unknown" and "0xFFE0 - 0xFFFF UINT 65504 - 65535 ..."; "0xFFC0 ANY 65472 ... A Modbus register is not supported".
- **Detail:** Expressible today as an `invalid` list of 33 values per point, which is verbose and error-prone. Should 6.6 accept ranges? Same theme as c01-msw-overflow-sentinel. Not blocking: DM3500 is needs-check for the address base.

### `c09-smartgen-hgm6120t-split-counters`: Run hours, start count and energy are MSB/LSB register pairs with range 0-9999 each; the combination is not stated.

- **Class 9, vendor:** SmartGen (HGM6120T)
- **Owner:** vendor
- **Decision:** D6
- **Evidence:** HGM6120T protocol 1.0 p.16, Table 24: "0042 Oil Engine Total Running Time (h) MSB Unsigned (0-9999)", "0043 ... (h) LSB Unsigned (0-9999)", "0046/0047 Total Start Times MSB/LSB", "0048/0049 Total Energy MSB/LSB", all "(0-9999)".
- **Detail:** The ranges suggest value = MSB x 10000 + LSB, which the draft cannot express (6.4 converts one raw value; u32 combines in base 65536); c08-schneider-energy-decades is the same gap in base 1000. Kept as a question because the document does not state the formula. If SmartGen confirms it, it is a D6 spec-gap with regression 0042 = 0x0001, 0043 = 0x0BB8 -> 13000 h.

### `c09-woodward-bitlist-int16`: BITLIST registers declared int16 are read as u16 for mask and flags.

- **Class 9, vendor:** Woodward (easYgen-3200XT)
- **Owner:** maintainer
- **Decision:** D6
- **Evidence:** B37574 50099 Control mode "int16 BITLIST" Mask 000Fh (p. 991); 50120 Alarms 1 latched int16 BITLIST (p. 999).
- **Detail:** Spec 6.3 allows masks only on u16/u32/u64, so the declared int16 cannot carry the mask. Reading the same 16 bits as u16 gives identical bits. Should the draft say that a mask or flag set reads the register as unsigned regardless of a vendor's declared signedness, or allow masks on signed types?

### `c09-woodward-exponent-stability`: The exponent registers are configuration parameters; their stability is left at the default.

- **Class 9, vendor:** Woodward (easYgen-3400, easYgen-3500, easYgen-3200XT)
- **Owner:** maintainer
- **Decision:** D9
- **Evidence:** 37528J p. 405 / B37574 p. 633-634: parameters 3181-3183 "adjust the format of the 16 bit ... values in the data telegram"; Protocol 5010 rows 450002-450004 / 50001-50003.
- **Detail:** W005 expects a referenced scale factor to be constant or session. The manuals present these as settings but do not say whether they can change while connected (parameters are writable over Modbus), so the points carry no stability. Should configuration-backed scale factors be marked session?

### `c10-config-selected-unit`: Internal temperature unit (°C/°F/K) is chosen by a device setting that the S-series map does not expose.

- **Class 10, vendor:** EKO Instruments (MS-60S)
- **Owner:** maintainer
- **Decision:** D13 (D3)
- **Evidence:** MS-60/MS-60S manual Ver. 5, p64 Table A4-9 register 22-23 "Unit: (°C / °F / K)"; the temperature unit setting is made in the Hibi software.
- **Detail:** The unit is omitted and explained in the description. Variants (5.6) are defined for firmware/hardware subsets and corpus/run.py cannot emit them; should configuration-selected units be expressed as variants, or stay out of scope?

### `c10-register-type-profiles`: Register 103 switches registers 0-49 between four maps (S-, M-, SMP-, SRD-series); only the default S-series is mapped.

- **Class 10, vendor:** EKO Instruments (MS-40S, MS-60S, MS-80S)
- **Owner:** maintainer
- **Decision:** D3 (D7)
- **Evidence:** MS-80S manual Ver. 8 p64 "The contents of registers No. 0 to 49 are switched according to the register type setting (No.103)"; p67-68 Tables A4-9 to A4-12; the M-series map (Table A4-10) stores floats LSW first (Sensitivity LSW at 16, MSW at 17). The numeric values of register 103 are not documented.
- **Detail:** Separate contracts per profile or variants keyed by a configuration register? run.py has no way to pass variants from an extractor. Contracts are named s-series so other profiles can be added.

### `c10-scaling-factor-register`: Registers 8 and 9 "Scaling factor irradiance/temperature, Default = 100" have no stated effect on the data registers.

- **Class 10, vendor:** Hukseflux (SR20-D2)
- **Owner:** vendor
- **Decision:** D9 (D6)
- **Evidence:** SR20-D2 manual v2404, p34 Table 6.3.4 rows 8 and 9; p35 "Register 8, Scaling factor irradiance, default scaling factor is 100."
- **Detail:** The manual gives irradiance in fixed 0.01 W/m2 units, matching the default 100. If a different value changes the resolution as a divisor, the draft cannot express it (same shape as c10-negated-scale-factor). Mapped as a plain u16 with fixed exponent10 -2 on the irradiance; needs vendor confirmation.

### `c10-coherent-multiword-read`: Vendor requires the MSW and LSW of a 32-bit value in one request; the draft does not say a multi-register point is read in one request.

- **Class 10, vendor:** Hukseflux (SR20-D2, SR30-M2-D1)
- **Owner:** maintainer
- **Decision:** D10
- **Evidence:** SR20-D2 manual v2404 p35 "MSW and LSW should be read together in one request"; SR30-M2-D1 manual v2508 p84 "both 16 bit Modbus registers must be read in a single Modbus request".
- **Detail:** Section 7 lets runtimes plan reads freely within maxReadRegisters. Should the draft state that a multi-register point is never split across requests, or should constraints be able to say so?

### `c10-vendor-function-code`: Serial number, firmware version and bus parameters are only available through vendor function code 0x46.

- **Class 10, vendor:** IMT Technology (Si-RS485TC-T-MB, Si-RS485TC-2T-MB, Si-RS485TC-T-Tm-MB)
- **Owner:** maintainer
- **Decision:** D3
- **Evidence:** Modbus Specification Si-RS485…-MB (January 2026), p1 and p2 "0x46: Communication Parameter".
- **Detail:** Contracts stay at 4-5 points because the standard register map has nothing else. Is identity data behind a user-defined function code in scope for a device contract?

## Document ambiguities

### `c01-cg-overflow-word-order`: EM511 overflow 0x7FFFFFFF read as the decoded INT32 value under LSW-first order.

- **Class 1, vendor:** Carlo Gavazzi (EM511)
- **Owner:** vendor
- **Evidence:** EM511 rev 1.8 p.11 section 3.3: 'represented as 0x7FFF for 16-bit registers, 0x7FFFFFFF for 32-bit registers'; p.10 LSW->MSW.
- **Detail:** Mapped invalid: [2147483647] (wire [0xFFFF, 0x7FFF]). If the meter puts 7FFF first on the wire the sentinel would never match; a device test would settle it.

### `c01-schneider-word-order`: DOCA0005EN never states the register order of Float32, UInt32 or Int64 values.

- **Class 1, vendor:** Schneider Electric (iEM3155, iEM3255, iEM3355)
- **Owner:** vendor
- **Evidence:** DOCA0005EN-16 p.56 'Unit table' defines the types; no word-order statement or worked example anywhere (searched for order, significant, endian, MSW/LSW, example frames).
- **Detail:** Blocks every core measurement (p.66-68). Needs a Schneider source that states the order (e.g. a Modbus FAQ or register-list file) before mapping. Also note the edition-pinned URL in this report.

### `c01-schneider-int64-signedness`: Int64 is defined as unsigned on p.56 but called signed on p.67.

- **Class 1, vendor:** Schneider Electric (iEM3155, iEM3255, iEM3355)
- **Owner:** vendor
- **Evidence:** DOCA0005EN-16 p.56 'Int64 64 bit unsigned integer 0 to 18 446 744 073 709 551 615'; p.67 'available in both signed 64-bit integer and 32-bit floating point format'.
- **Detail:** Decide u64 vs i64 once word order is known.

### `c01-cg-int64-word-order`: 64-bit Wh energy rows are INT64, a format the data-format table does not define.

- **Class 1, vendor:** Carlo Gavazzi (EM511, EM530, EM540)
- **Owner:** vendor
- **Evidence:** EM511 p.15 / EM530-EM540 p.17 Table 4.3 0500h 'kWh (+) TOT' 4 words INT64 'Value weight: Wh'; p.10 section 3.1 lists UINT64 (not INT64) with LSW->MSW.
- **Detail:** Signedness and word order of INT64 are not stated; the 64-bit energies are left out.

### `c01-cg-request-limit`: Read limit stated as 125 registers in text but 1-20 in the frame table.

- **Class 1, vendor:** Carlo Gavazzi (EM511, EM530, EM540)
- **Owner:** vendor
- **Evidence:** EM511 p.5-6 / EM530-EM540 p.5-6: 'It is possible to read maximum 125 registers' vs 'Quantity of registers (N word) 1 to 14h (1 to 20)'.
- **Detail:** No maxReadRegisters set. A device test or vendor answer should decide.

### `c01-eastron-holding-gaps`: Holding parameters with unclear encoding: 2-byte Hex values in 2-register slots, uint32 serial word order, missing Register Order row.

- **Class 1, vendor:** Eastron (SDM230, SDM630)
- **Owner:** vendor
- **Evidence:** SDM230 p.5 463761 (F910h) Pulse 1 constant and 463776 (F920h) Measurement mode 'Data Format: Hex (length: 2 byte)' while p.2 requires even register counts and single-register reads return an instrument type value; SDM230 p.5 / SDM630 p.7 464513 (FC00h) Serial number 'unsigned int32' (word order stated only for floats); SDM230 p.1 and SDM630 p.1/p.7 refer to a 'Register Order' holding register that neither table lists.
- **Detail:** All left out. If the 2-byte value sits in the first register of the pair, it could be a u32 with mask 0xFFFF0000; needs vendor confirmation.

### `c01-abb-flag-words`: 64-bit Error/Information/Warning/Alarm flag words have no bit definitions.

- **Class 1, vendor:** ABB (B21, B23, B24)
- **Owner:** vendor
- **Evidence:** B21 p.75 / B23-B24 p.91: 8A13, 8A19, 8A1F, 8A25 '64 flags', 4 registers, 'Bit string'.
- **Detail:** Not mapped; a flags point needs named bits.

### `c02-abb-product-type-dtype`: The product type ID row has no data type, so the point is left out.

- **Class 2, vendor:** ABB (M4M 20 Modbus, M4M 30 Modbus, M4M 2X Modbus)
- **Owner:** vendor
- **Evidence:** 'Mapping Table' row 299, Product type number ID, 0x8910, 1 register, Data Type and Resolution empty, Details "See Details sheet".
- **Detail:** Reading it as u16 would be a signedness guess, so it was dropped from the contracts (19 points). With a stated data type it becomes an enum over the Details sheet IDs 0 to 30. Ask ABB to fill in the data type.

### `c02-abb-quadrant-enum`: The current-quadrant registers have no documented values.

- **Class 2, vendor:** ABB (M4M 20 Modbus, M4M 30 Modbus, M4M 2X Modbus)
- **Owner:** vendor
- **Evidence:** 'Mapping Table' row 59, Current quadrant, Total/L1/L2/L3, 0x5B44 (23364), 4 x 1 register, Unsigned.
- **Detail:** Left out. Map it as an enum once ABB documents which value means which quadrant.

### `c02-janitza-base-inferred`: The zero base and the holding-register table are logically forced by the list, not stated; please confirm.

- **Class 2, vendor:** Janitza electronics (UMG 96RM, UMG 96RM-E, UMG 96RM-PN)
- **Owner:** maintainer
- **Decision:** D4
- **Evidence:** DE and EN lists, PDF p.14: the parameter table starts at address 0 (device address, SHORT RD/WR). PDF p.4 "Modbus functions (slave)": 03 Read Holding Registers and 04 Read Input Registers are both listed, with 06/16 presetting holding registers (4X references); no sentence says which table the address list is, or that its addresses are PDU addresses.
- **Detail:** Mapped under rule 3: zero-based because the list contains address 0, holding registers because read-only and writable (FC 06/16) rows share one list; one sentence says so in info.description of the three contracts. The extractor requires the address-0 row and the slave function list. FC 04 may serve the same addresses, which the document also does not state. A Janitza statement or a device test would settle it.

### `c02-siemens-word-order`: The PAC manuals state neither the meaning of "Offset" (PDU address or register number) nor the word order of float, unsigned long and double values.

- **Class 2, vendor:** Siemens (SENTRON PAC2200, SENTRON PAC3120, SENTRON PAC3220)
- **Owner:** vendor
- **Decision:** D4, D5
- **Evidence:** PAC2200 manual L1V30415167B-06 PDF p.107: measured values start at offset 1 (Voltage UL1-N, Float, 2 registers). PAC3120/PAC3220 manual L1V30425208F_RS-AA_002 PDF p.113: offset 1 Voltage L1-N; PDF p.122 (A.1.6): FC 0x02 offsets start at 0; PDF p.121 Table A-6: byte 0 = mask 0x01000000 (most significant byte); PDF p.137 (A.1.8 LED example): "Byte 3" transmitted first.
- **Detail:** Not mapped. Needs a Siemens statement (or a worked request example with addresses and payload) for the base and the word order, or a device test the maintainer accepts as evidence.

### `c02-schneider-base-wordorder`: The PM5000 register lists state neither whether "Register" is zero- or one-based nor the word order of 32/64-bit values.

- **Class 2, vendor:** Schneider Electric (PM5110, PM5330, PM5560)
- **Owner:** vendor
- **Decision:** D4, D5
- **Evidence:** PM556x workbook (sha256 312c4859..., Revision 1.4): 'Register List' column P "Register", e.g. P230 = 3084 Power Factor Total; no base or order statement on any sheet. User manual HRB1684301-18: not stated. FAQ FA332210: register offsets vary by meter.
- **Detail:** Not mapped. Needs a Schneider document that states the base (for example "register N is read at address N-1") and the word order for PM5000 meters.

### `c03-fronius-word-order`: No stated register order for 32/64-bit values; AC lifetime energy left out.

- **Class 3, vendor:** Fronius (Primo 3.0-1, Primo 4.0-1, Primo 5.0-1)
- **Owner:** vendor
- **Evidence:** Inverter_Register_Map_Int&SF_v1.0: WH 40094-40095 uint32 (Complete Map row 51), Evt1 40110-40111 uint32, ActWh 40187-40190 acc64, F_Site_Energy_Total 510-513 uint64. Datamanager manual 033-24022026 only says '2 registers = 32 bit value' and refers to the SunSpec Alliance specifications for register addresses. Its worked read covers a string only (byte order within a register, ascending registers), not a 32-bit value.
- **Detail:** SunSpec itself is high word first, but neither Fronius document (including the pinned Datamanager manual) says so. Either the vendor states it, or the maintainer admits a pinned SunSpec specification as evidence; then add WH (u32, exponent10 WH_SF) and the event flags.

### `c03-fronius-st-used-column`: St.csv/StVnd.csv have an unexplained fifth yes/no column.

- **Class 3, vendor:** Fronius (Primo 3.0-1, Primo 4.0-1, Primo 5.0-1)
- **Owner:** vendor
- **Evidence:** St.csv: '2,2,I_STATUS_SLEEPING,Sleeping (auto-shutdown),no', '6,...SHUTTING_DOWN...,no'.
- **Detail:** Probably whether Fronius reports the state; the enum keeps all values since unknown or unused values are harmless. Needs a vendor statement.

### `c03-solis-address-notation`: Section 3.3 gives Modicon-style ranges (30001-39999, 40001-49999) but the tables and examples use plain PDU numbers.

- **Class 3, vendor:** Solis (S6-GR1P4K, S6-GR1P5K, S6-GR1P6K)
- **Owner:** vendor
- **Evidence:** Page 5 function-code table vs page 6 rows 2999-3545 and 35000; examples 6.1/6.2 '0B B6' = 2998, '0B B7' = 2999.
- **Detail:** Rows 2998-3053 are resolved by the worked examples and the contracts use them as PDU addresses. Register 35000 (Inverter Type) is left out: under the 30001-39999 remark it could mean PDU 4999 or 35000, and no example covers it.

### `c04-fronius-word-order`: Register order of 32/64-bit SunSpec values is not stated, so alarm bitfields and energy counters are left out.

- **Class 4, vendor:** Fronius (Symo GEN24 6.0 Plus, Symo GEN24 8.0 Plus, Symo GEN24 10.0 Plus)
- **Owner:** maintainer
- **Evidence:** Complete Map rows Evt1 (register 40110, bitfield32), EvtVnd1 (40114, bitfield32, bit 0 Error, bit 1 Warning, bit 2 Info), WH (40094, acc32), ActWh (40187, acc64), module/3/DCWH (40316, acc32). Only the SID row (40001, uint32, "0x53756e53 ('SunS')") shows a 32-bit value together with its text, which implies the high word first; neither the workbook nor the manual says so.
- **Detail:** Maintainer to decide whether the SunSpec convention, or the SID example, is sufficient evidence. If yes, add EvtVnd1 as a u32 flags point (core alarm flags of this class) and WH as u32 with WH_SF.

### `c04-outback-block-relative`: The AXS app note gives only block-relative 1-based offsets; no base address or block order.

- **Class 4, vendor:** OutBack Power (Radian GS4048A, Radian GS8048A, FXR3048A)
- **Owner:** vendor
- **Decision:** D12
- **Evidence:** axs_app_note.pdf (Rev 5) page 1 "Columns": Start/End are "offset from the beginning of the block"; every DID field is at Start 1; no 40000/40001 base anywhere in the 24 pages; blocks are assembled per connected product; "should be used as examples only".
- **Detail:** Needs a vendor statement of the SunSpec base register and the block order for a given AXS Port configuration, or the planned sunspec discovery profile (spec section 10) to walk the chain at runtime. Draft groups with a base address and offsets could hold the blocks once a base is known.

### `c04-schneider-word-order`: Register order of uint32/sint32 and character order of str<nn> are not stated, so battery V/I/P are left out.

- **Class 4, vendor:** Schneider Electric (Conext SW 2524 230, Conext SW 4024 230)
- **Owner:** vendor
- **Evidence:** 503-0244-01-01 page 2 Table 2 Modbus Data Types (uint32, sint32, str<nn> "Two characters are packed into each Modbus register") gives no order. Affected core rows: 0x004E Battery Voltage uint32, 0x0050 Battery Current sint32, 0x0052 Battery Power sint32, 0x0084 Load AC Power uint32.
- **Detail:** A vendor statement (or a worked multi-register example) would let these core points be added.

### `c04-schneider-table-and-transport`: No pinnable document names the function codes; holding_register is forced by the map (rule 3), serial framing unknown.

- **Class 4, vendor:** Schneider Electric (Conext SW 2524 230, Conext SW 4024 230)
- **Owner:** maintainer
- **Evidence:** 503-0244-01-01 and 503-0253-01-01 contain no function code or "holding" wording; Table 3 mixes r and rw rows in one address space. The pinned ComBox datasheet DS20130702_ConextComBox states the Modbus TCP/IP server and an RS485 "Modbus ... 2-wire serial, 19200bps" port, but no function codes and no RTU/ASCII framing. The ComBox and Modbus Converter owner's guides (975-0679-01-01, 975-0685-01-01) are on solar.se.com only (403) or third-party mirrors; download.se.com returns 404 for 975-0679-01-01.
- **Detail:** Maintainer to confirm that read-only rows are served by FC 03 (holding registers). The contracts say in info.description that the table follows from the shared r/rw register list. The rtu transport (Modbus Converter or ComBox RS485) was removed; add it back when a pinnable document states the framing.

### `c04-victron-word-order`: The register list does not state the word order of uint32/int32 registers.

- **Class 4, vendor:** Victron Energy (MultiPlus-II, Quattro, EasySolar-II GX)
- **Owner:** vendor
- **Evidence:** Field list rows: vebus 74-93 uint32 energy counters (Scalefactor 100, kWh), 96/98/100 int32 ESS power setpoints, 130-136 uint32 nominal inverter power; no order statement in the workbook or the GX Modbus-TCP Manual.
- **Detail:** A vendor statement would let 32-bit energy counters be added.

### `c05-comem-register-model`: Appendix A gives hex register addresses but no table, function code, base, type, scale or unit.

- **Class 5, vendor:** COMEM (eOTI, eWTI, CU eOLI)
- **Owner:** vendor
- **Evidence:** Temperature indicators manual p. 34 Table 5 (0x2000 "PT100 value", 0x2003/0x2004 day max/min, 0x200A software version); CU eOLI manual p. 34 Table 4 (0x2000 "Filling percentage 0%..100%", 0x2001 relay status bit 0, 0x2009 "Conservator filling in [mm]"). Operation column "R" only; p. 7 says "for more information contact COMEM".
- **Detail:** Without the function code (holding or input registers), the address base, and the raw type and scaling of "PT100 value", no point can be mapped without guessing. Ask COMEM for a Modbus register description, or confirm on a device.

### `c05-reinhausen-multiplier-direction`: The Multiplier/Scale column does not say whether the raw value is multiplied or divided.

- **Class 5, vendor:** Maschinenfabrik Reinhausen (TAPCON 230 AVT, 250, 260)
- **Owner:** vendor
- **Evidence:** TAPCON 230 AVT Table 8 (p. 19): Measured Voltage 0..4800, Multiplier 10, V; TAPCON 250 6.3 (p. 6): measured voltage Scale 10, Volts; TAPCON 260 Table 12 (p. 17): Measured voltage 0..1,700, Multiplier 10, V; currents with 100 and "100 % = 200 mA".
- **Detail:** The ranges suggest raw / factor (e.g. 1,700 / 10 = 170.0 V on a VT secondary), but the documents never say so, and "Multiplier" reads as raw x factor. Regulated voltage, voltage deviation, currents and frequency were therefore left out of all three contracts, although regulated voltage is a core point of this class. Confirm with Reinhausen or on a device, then add those points with exponent10 -1/-2.

### `c05-tapcon-230-avt-address-example`: The addressing example contradicts the PDU-address statement next to it.

- **Class 5, vendor:** Maschinenfabrik Reinhausen (TAPCON 230 AVT)
- **Owner:** maintainer
- **Evidence:** p. 11, 3.2: "Addresses in this document refers to the MODBUS PDU addresses. Example: Reading input status with address 8 will read address 7 in the Discrete Input block of the MODBUS data model."
- **Detail:** The mapping follows the explicit PDU statement and the zero-based tables (input status 0 = Desired Voltage Level 1). The example only makes sense as "data-model element 8 is PDU address 7"; confirm on a device by reading discrete input 3 (Auto/Manual) while switching the mode.

### `c05-tapcon-260-local-remote-polarity`: Input 16 "Local/remote" does not say which state is 1.

- **Class 5, vendor:** Maschinenfabrik Reinhausen (260)
- **Owner:** vendor
- **Evidence:** Table 10 (p. 16), address 16.
- **Detail:** Mapped as a bool with that note. TAPCON 230 AVT uses 1 = Remote, TAPCON 250 uses 1 = local, so no convention can be assumed.

### `c05-tecsystem-t1048-fault-relay`: The T1048 relay status fault bit reads "1=No Fault", NT935 says "1=ON".

- **Class 5, vendor:** TECSYSTEM (T1048 with Modbus)
- **Owner:** vendor
- **Evidence:** T1048 RELAY STATUS note (p. 26) bit 4 "FAULT Relay 1=No Fault"; NT935 AD/ETH bit 4 "FAULT Relay 1=ON".
- **Detail:** Both labels are kept verbatim. The fault relay is normally energized, so both may be true, but check on a device.

### `c05-tecsystem-options-bit-order`: The Options register note writes two-bit values as "Bit_0/1 = 10" without the bit order.

- **Class 5, vendor:** TECSYSTEM (NT935 AD, NT935 ETH, T1048 with Modbus)
- **Owner:** vendor
- **Evidence:** Mapping table address 6 "Options (see note)"; note NT935 AD p. 21 (ETH p. 19, T1048 p. 21): HIGH Byte "Bit_0/1 = 00 - Range 0°C - 240°C", "Bit_0/1 = 10 - Range -40°C ÷ +200°C".
- **Detail:** This register tells which temperature range version (the "(*)" ranges) a unit is, but "10" does not say which of bit 0 and bit 1 is set. Not mapped; the temperature descriptions give both ranges.

### `c05-opt100-f64-word-order`: The 64-bit float measurement timestamp has no stated word order.

- **Class 5, vendor:** Vaisala (OPT100)
- **Owner:** vendor
- **Evidence:** Table 33 (p. 130) register 161, 0x00A0..0x00A3 "Time stamp of result set, in seconds since epoch", 64-bit float.
- **Detail:** A.3 only defines the order for 32-bit values. Left out. The 64-bit test registers (0x00CB u64, 0x00D8 f64, p. 140) could settle the order on a device.

### `c05-opt100-scaled-int-notation`: OPT100 scaled 16-bit units ("ppmw*10", "°C*10", "ppmv*0.1") are not defined in this guide.

- **Class 5, vendor:** Vaisala (OPT100)
- **Owner:** vendor
- **Evidence:** Table 33 present values as 16-bit signed integer (pp. 131-132), e.g. 229 Moisture in oil "ppmw*10", 233 Oxygen "ppmv*0.1".
- **Detail:** The MHT410 guide (B.3.2) defines the notation; the OPT100 guide does not, and "*0.1" could mean either direction. Only the unscaled methane value is mapped.

### `c06-abb-default-offset`: The REF615 and REM615 point lists and their protocol manual give default scale factors but no default offset, so their measurands are excluded.

- **Class 6, vendor:** ABB (REF615, REM615)
- **Owner:** maintainer
- **Evidence:** 1MRS756468 rev. R 3.4.5: "Modbus value = ( IEC 61850Value × scaleFactor ) + Offset" and "there always exists a scaleFactor and an offset parameter for each Modbus register value"; table 11 gives Offset "Any real value" with no default. The REF615 point list columns list only "Scale Scale factor, default setting" (pdf page 17); REM615 lists "Offset Offset factor, default setting" among its column explanations (pdf page 15) but its register table has no Offset column. Only the RET615 ANSI point list (5.0 FP1, table 110, pdf page 71) says "an adjustable offset value exists that is set to 0 by default"; 3.4.5.2 says per-unit values are shown "multiplied with the scaleFactor 1000" by default.
- **Detail:** Decided under rule 4 of the evidence policy: the REF615 and REM615 measurands (every Table 2 register row, since each carries a scale) are excluded until the default offset is confirmed for REF615 Ver. 3.0 and REM615 Ver. 2.0, and info.description says so. Both models stay mapped with their indication bits (7 points each). RET615 5.0 FP1 is not affected: its own point list states the offset is 0 by default. To restore the measurands, ABB (or an edition of the point lists or protocol manual for these versions) has to state the default offset; the extractor would then require that statement as it does for RET615.

### `c06-siemens-profile-manual`: The bus mapping gives no register data types or word order; they are in a separate communication profile manual.

- **Class 6, vendor:** Siemens (7SJ80, 7SK80, 7RW80)
- **Owner:** maintainer
- **Evidence:** Bus mapping pdf page 3 refers to "SIPROTEC communication modules, Modbus - Communication profile", C53000-L1840-C001-03, for data types, "Absolute time", double-point indications and scaling changes. Chapters 1.6.4/1.6.5 (metered and statistic values, 32-bit) and coils 00001/00002 (breaker) depend on it.
- **Detail:** Only magnitude input registers are mapped, as i16 whose documented range 0...32767 decodes the same signed or unsigned. P, Q and PF (signed), the 32-bit metered values, the breaker double points and the min/max time stamps are left out. Pin the profile manual as a second source to map them.

### `c06-fanox-float-format`: The measurement maps use FLOAT / FLOAT INVERSE, which the manuals do not define consistently, and give no units.

- **Class 6, vendor:** Fanox (SIL-A, SIA-C, SIA-B Specific CT)
- **Owner:** vendor
- **Decision:** D5
- **Evidence:** SIA-B Rev. 02 data types (pdf page 5) define only "FLOAT 2 Number in floating decimal point 'Float' of 4 bytes", but its measurement map (pdf page 10) uses "FLOAT INVERSE". SIA-C Rev. 03 (pdf page 6) and SIL-A Rev. 05 (pdf page 6) read "Number in FLOAT INVERSEing decimal point 'FLOAT INVERSE' of 4 bytes", apparently a text replacement. The measurement rows (for example SIA-B 300 "Phase A current IA") carry no unit.
- **Detail:** "INVERSE" may mean low word first, but that is a guess, so no float is mapped. Ask Fanox to define FLOAT and FLOAT INVERSE (word and byte order) and to give units. With that, the phase currents and the thermal image become mappable as f32.

### `c06-fanox-sia-b-star-mark`: The SIA-B states map marks words and states with (*) but does not say what the mark means.

- **Class 6, vendor:** Fanox (SIA-B Specific CT)
- **Owner:** vendor
- **Evidence:** SIA-B Rev. 02 states map (pdf pages 7-10): "Pickup (*)", "49 (*)", "Trip Block (*)", "Remote Modbus (*)". The SIA-C manual explains the same mark as "(*) Depending on model." (pdf page 14). In SIA-B's settings maps "(*)" means "Read/Write Address".
- **Detail:** The points carry a description saying the mark is unexplained. If it means model-dependent, the 49 word may be absent on some SIA-B variants.

### `c07-adam-address-base`: The ADAM-6000 manual's request examples contradict each other and the usual 1-based reading of its references.

- **Class 7, vendor:** Advantech (ADAM-6050, ADAM-6051, ADAM-6060)
- **Owner:** vendor
- **Evidence:** ADAM-6000 User Manual Ed. 12, Appendix B.1 (PDF pp. 197-200): FC 01 "Read Coils 1~8 (Addresses 00017~00024)" sends start bytes "00 17" (0x0017 = 23); FC 15 "starting at Address 00017 ("11" in hex)" sends 0x0011 = 17; FC 02 "Addresses 00001~00008" sends 0x0001; FC 04 "Addresses 40001~40002" sends 0x0001; FC 06 "Preset Register 40002" sends 0x0002; FC 05 "Coil 3 (Address 00003)" sends 0x0003.
- **Detail:** Read literally, reference n is PDU address n (not n-1), and the FC 01 example writes the decimal reference as hex. The B.2 tables give only 5-digit references, so the base cannot be resolved from the document. Ask Advantech (or test a device) whether 00001/40001 is PDU address 0; then map from B.2.

### `c07-adam-di-table`: Digital inputs are listed in "Address (0X)" (coil) notation but read with function 02 in the examples.

- **Class 7, vendor:** Advantech (ADAM-6050, ADAM-6051, ADAM-6060)
- **Owner:** vendor
- **Evidence:** Appendix B.2, ADAM-6050 table "Address (0X)" 00001-00012 "DI value" Read (PDF p. 214); ADAM-6060/6066 "Address (0X)" 00001-00006 DI value (PDF p. 227); B.1 FC 02 example "Read coils 1~8 (Addresses 00001~00008)" (PDF p. 197).
- **Detail:** Whether the inputs are coils (FC 01), discrete inputs (FC 02) or both must be confirmed before mapping the table.

### `c07-stride-base-derived`: The Stride guides never state the reference base; the contracts derive 1-based from the coil mirror diagrams.

- **Class 7, vendor:** AutomationDirect (SIO-MB12CDR, SIO-MB16CDD2, SIO-MB08THMS)
- **Owner:** maintainer
- **Evidence:** PDF p. 2 (tables, "0xxxx and 1xxxx = Coils (bit)", "3xxxx and 4xxxx = Registers (word)"); PDF p. 4 40011 System Flags diagram: coils 161, 162, 163 at bits 8, 9, 10; PDF pp. 4-5 40031/40032 diagrams: Output/Input #n at bit n with coils 00489/00505 for #0.
- **Detail:** Only 1-based references fit every diagram (coil c in register 40001 + (c-1) div 16 at bit ((c-1) mod 16) XOR 8, which is FC 01 coil packing in wire byte order); 0-based readings fit none. The extractor checks each mirrored bit. The maintainer should accept this derived evidence or ask AutomationDirect to state the base; a device test would settle it.

### `c07-stride-counter-word-order`: The 32-bit input counters use two registers each, but the word order is not stated.

- **Class 7, vendor:** AutomationDirect (SIO-MB12CDR, SIO-MB16CDD2)
- **Owner:** vendor
- **Evidence:** SIO-MB12CDR guide PDF p. 5, "40039-40040: 32-BIT COUNTER DIGITAL INPUT 0" ... "stored as unsigned 32-bit integers, using two registers each"; no high/low word statement anywhere in the guide.
- **Detail:** Counters (a class core point) are left out of both contracts until the order is confirmed.

### `c07-moxa-scaled-value-type`: The two-word AI scaled values have a stated word order but no stated data type.

- **Class 7, vendor:** Moxa (ioLogik E1240)
- **Owner:** vendor
- **Evidence:** ioLogik E1200 manual Appendix A, E1240 map (PDF p. 106): AI_scaledValue 0008/30009, AI_scaledValueMin 0109/30110, AI_scaledValueMax 0125/30126, "high/low word", 2 words. Only the EtherNet/IP object table (a different protocol) lists aiValueScaled as REAL.
- **Detail:** Confirm whether the Modbus scaled value is an IEEE-754 float (f32, high word first) or an integer.

### `c07-moxa-two-word-order`: deviceUpTime and firmwareBuildDate span two registers without a stated word order.

- **Class 7, vendor:** Moxa (ioLogik E1210, ioLogik E1212, ioLogik E1240)
- **Owner:** vendor
- **Evidence:** Appendix A system tables (e.g. E1210, PDF p. 97): deviceUpTime 5020/35021, Length 2, "unit: sec(s)"; firmwareBuildDate 5031/35032, Length 2, "e.g. Build16051718 --> 16051718". Counter rows say "high/low word"; these rows do not.
- **Detail:** Left out of the contracts. The counter rows suggest high word first, but that is not stated for these rows.

### `c07-icp-das-frequency-unit`: The DI frequency row gives the x1000 scale but no unit; the contract omits the unit.

- **Class 7, vendor:** ICP DAS (ET-2251)
- **Owner:** maintainer
- **Evidence:** Section 6.3 3xxxx table, address 64 (0x40) "The frequency Value is * 1,000. (Note: The Client must first divide the value by 1,000.)" (PDF p. 180). The configuration chapter describes frequency ranges in Hz (e.g. "0.01 Hz to 3.5 kHz").
- **Detail:** The maintainer can decide whether the configuration chapter is enough evidence to add unit Hz.

### `c08-danfoss-fc300-address-base`: The Design Guide's parameter-to-register formula conflicts with the FC 51 rule and gives no base.

- **Class 8, vendor:** Danfoss (FC 301, FC 302)
- **Owner:** vendor
- **Evidence:** MG33BF02 PDF p. 188 (section 12.12.1): "(10 x parameter number) DECIMAL", example 3-12 in holding register 3120 and 3-14 in 3410 & 3411. FC 51 MG.02.A4.02 p. 30 states 10 x PNU - 1.
- **Detail:** Unclear whether 3120 is the PDU address or a 1-based register number. Resolve from the FC 301/302 Programming Guide or a Danfoss Modbus RTU document with a byte-level example.

### `c08-danfoss-fc51-uint8`: The register layout of Uint8 parameters is not stated.

- **Class 8, vendor:** Danfoss (FC 51)
- **Owner:** vendor
- **Evidence:** MG.02.A4.02 p. 58 16-18 Motor Thermal and 16-34 Heatsink Temp. are Uint8; p. 45 lists data type 5 Uint8.
- **Detail:** Not stated whether a Uint8 occupies the low byte of the register; motor thermal and heatsink temperature left out.

### `c08-danfoss-fc51-dc-link-unit`: 16-30 DC Link Voltage has no unit in the manual.

- **Class 8, vendor:** Danfoss (FC 51)
- **Owner:** vendor
- **Evidence:** MG.02.A4.02 p. 44 shows "16-30 DC Link Voltage" without a bracketed unit; p. 58 conversion index 0.
- **Detail:** Mapped without unit. Confirm the unit (expected volts) from another Danfoss document.

### `c08-automationdirect-signedness`: The status address list gives no signedness for torque and motor speed.

- **Class 8, vendor:** AutomationDirect (GS20, GS30, GS4)
- **Owner:** vendor
- **Evidence:** GS20 p. 297 210Bh "Output torque (XXX.X %)", 210Ch "Actual motor speed (XXXXX rpm)"; GS4 p. 313 210Ch "Motor Actual RPM".
- **Detail:** Both can be negative in reverse or regenerating operation; left out until the format is stated.

### `c08-automationdirect-output-current`: Output current shifts its decimal place above 655.35 A without a stated encoding.

- **Class 8, vendor:** AutomationDirect (GS20, GS30)
- **Owner:** vendor
- **Evidence:** GS20 p. 297, 2104h and 2200h: "When the current is higher than 655.35, it automatically shifts one decimal place"; "Refer to the high byte of 211F for information on the decimal places".
- **Detail:** If the 211Fh high byte is stated to hold the number of decimals, this may be expressible with exponent10 referencing a point holding the negated decimal count; until then left out.

### `c08-automationdirect-gs2x-output-power`: 210Fh output power has conflicting scale statements.

- **Class 8, vendor:** AutomationDirect (GS20, GS30)
- **Owner:** vendor
- **Evidence:** GS20 p. 297 210Fh "X.XXX kW" versus 2114h "Indicates one or two decimal points for value in 210F".
- **Detail:** Left out; output power is mapped from 2206h (XXXX.X kW) instead.

### `c08-automationdirect-gs4-scales`: GS4 frequency, current and power status registers have conflicting or no scales.

- **Class 8, vendor:** AutomationDirect (GS4)
- **Owner:** vendor
- **Evidence:** GS4 p. 313 2102h/2103h "(xxx.x)" versus the 2001h example "6000 = 60.00Hz" on p. 483; 210Fh output power has no scale.
- **Detail:** Left out until the scale is confirmed.

### `c08-schneider-word-order`: 32-bit word order depends on parameter TWO, whose values are not defined.

- **Class 8, vendor:** Schneider Electric (ATV340, ATV630)
- **Owner:** vendor
- **Evidence:** NVE61728 Parameters row 1381 and EAV64332 row 1331, TWO at 16#1776 = 6006 (default HIGH, "Modbus Word Order ON").
- **Detail:** 32-bit values (for example RTH, PTH) are left out.

### `c08-schneider-lcr-scale`: Motor current LCR has no scale in the workbook.

- **Class 8, vendor:** Schneider Electric (ATV340, ATV630)
- **Owner:** vendor
- **Evidence:** NVE61728 Parameters row 26 and EAV64332 row 23, LCR at 16#0C84 = 3204, units "Refer to programming manual".
- **Detail:** Left out; see also c08-schneider-current-decade.

### `c09-datakom-coeff-column`: The COEFF column (x1, x10, x100) is not defined.

- **Class 9, vendor:** Datakom (D-300, D-500, D-700)
- **Owner:** vendor
- **Evidence:** V5.6 pp.11-16, register table column "COEFF."; no definition anywhere in the document. Example rows: 10339 "Genset frequency" x100, 10361 "Oil pressure in bars" x10, 10328-10335 power factor x10.
- **Detail:** Read as register = value x COEFF (exponent10 -2 for x100, -1 for x10), the only reading that gives plausible frequency and pressure values. The power factor rows at x10 would give a 0.1 resolution, which is unusual; they are not mapped. Frequency and battery voltage rows name no unit, so the contracts carry none. Confirm with Datakom.

### `c09-datakom-signedness`: Signedness of 16-bit registers is not stated, so temperatures are not mapped.

- **Class 9, vendor:** Datakom (D-300, D-500, D-700)
- **Owner:** vendor
- **Evidence:** V5.6 p.10 data formats give no integer encoding; only the scopemeter rows 10404-10503 (p.13) say "The register value is a signed integer." Temperatures that can be negative: 10362 "Engine temp in °C", 10364 "Oil temp in °C", 10365 canopy, 10366 ambient (x10).
- **Detail:** Non-negative quantities are mapped as u16. Engine (coolant) temperature, a class core point, is left out until Datakom confirms two's complement for these rows.

### `c09-deif-signedness`: The document never states whether 16-bit registers are signed or unsigned.

- **Class 9, vendor:** DEIF (AGC-3, AGC 110, AGC 111)
- **Owner:** vendor
- **Evidence:** 4189340442Z, measurement table pp.43-62: brackets give only unit and scale ([V], [Hz/100], [kW], [PF/100], [Deg/10]). No "signed", "two's complement" or similar anywhere in the document. p.157 (control registers) says a negative reactive-power setpoint "means capacitive", so negative values exist, but their encoding is not given.
- **Detail:** Left out the rows that can be negative: generator power 516-519 [kW], reactive power 520-523, PF 538 [PF/100] and phase angles 510-512 [Deg/10] (apparent power, cos-phi value and energy counters were not selected, to stay within 20 points). Voltages, currents, frequency, DC supply, RPM, counters and hour counters are mapped as u16 (or u32 for [Hi]/[Lo] pairs) on the assumption that they cannot be negative. The bit numbering of flag words (bit 0 = least significant) is likewise conventional, not stated. Confirm the integer format with DEIF before adding power or PF points.

### `c09-deif-agc110-tables-disagree`: The configurable area marks start attempts and run hours for AGC 110; the measurement table does not.

- **Class 9, vendor:** DEIF (AGC 110)
- **Owner:** vendor
- **Evidence:** 4189340442Z p.15, configurable area (function code 04h): address 29 "Start attempts" and 30 [Hi]/31 [Lo] "Abs. run hours" are marked X for AGC 110. Measurement table p.52 (554 [Hi]/555 [Lo] "Absolute. run hours") and p.53 (566 "Start attempts") leave the AGC 110 column empty.
- **Detail:** Not mapped for AGC 110 from either table. If DEIF confirms the configurable-area marks, add run hours and start attempts to the AGC 110 contract (from 554/555 and 566, as for AGC 111).

### `c09-kohler-address-base`: TP-6113 gives 4xxxx/40xxxx register numbers but no PDU mapping for the target controllers.

- **Class 9, vendor:** Kohler (Decision-Maker 550, Decision-Maker 3500, Decision-Maker 6000)
- **Owner:** vendor
- **Evidence:** TP-6113 12/21: DM550 table rows such as "400034 Coolant Temperature* RO SWORD Degrees C/Degrees F" (p.43); the note "Holding register 9999 may be illustrated as 49999 in the traditional format or as 409999 in the extended format" (pp.42, 83, 114). The only worked request, p.153 (section 9, Decision-Maker 8000): "Register number (Ubat => 40013) - 40013 - 40001 = 12 DEC => 000C HEX".
- **Detail:** The 4xxxx convention usually means PDU = number - 40001, but the brief forbids applying it without a statement for these sections, and the DM8000 example belongs to a different controller family. Ask Kohler to confirm "register 4xxxxx = PDU address xxxxx - 1" for DM550/3500/6000 (or test one register on a device), then map all three.

### `c09-smartgen-hgm6120t-overlapping-tables`: Two function 03H tables both start at address 0000 (a bit table and a register table).

- **Class 9, vendor:** SmartGen (HGM6120T)
- **Owner:** vendor
- **Evidence:** HGM6120T protocol 1.0 (2022-11-28): Table 20 "Function Code 03H, 06H Mapping Coil Field" (pp.11-13) lists one-bit rows 0000-00119 ("0000 Common Alarm 0 ... (LSB)", "0015 Undervoltage Alarm Shutdown ... (MSB)"); Table 24 "Function Code 03, 06 Corresponding Address" (pp.15-17) lists registers 0000-00123 ("0000 Mains UA Unsigned 2Bytes"). Table 4 (p.5) lists only 03H, 05H and 06H. Section 5.1 says 06H can write "0309-0314 and 0376-0387", addresses that appear in neither table.
- **Detail:** One of the two tables must be at other addresses (or Table 20 is a coil table read with a function the document does not list). The page looks adapted from another product. Ask SmartGen, or read register 0000 with function 03H on a device with known mains voltage, before mapping.

### `c09-smartgen-scale-marks`: The "(*10)", "(*100)" and "(*1000)" marks are not defined.

- **Class 9, vendor:** SmartGen (HGM9530N, HGM6120T)
- **Owner:** vendor
- **Evidence:** HGM9530N protocol 1.0 pp.12-18, e.g. "0155 Gen Frequency (*100)", "0213 Battery Voltage (*10)", "0201 Average Power Factor Signed (*1000)"; HGM6120T Table 24 "0013 Gen Frequency Unsigned (*10)". Neither document explains the mark (the HGM9510 document defines its Ratio column in NOTE1).
- **Detail:** Read as register = value x N (exponent10 -1/-2/-3), the only reading that gives plausible frequency, voltage and power factor values. Confirm with SmartGen.

### `c09-smartgen-hgm9530n-units`: The HGM9530N map has no unit column; voltages, currents, frequency, power and speed carry no unit.

- **Class 9, vendor:** SmartGen (HGM9530N)
- **Owner:** vendor
- **Evidence:** HGM9530N protocol 1.0 pp.12-18, columns "Address, Item, Description, Bytes" only.
- **Detail:** Units are set only where the item names one ("Total Running Time (Hour)" -> h); the other points say "The document states no unit for this register." Total active power is probably kW and battery voltage V, but the brief forbids guessing.

### `c09-smartgen-hgm9530n-word-order`: The order of 32-bit values comes only from LSB/MSB row labels, without a worked example.

- **Class 9, vendor:** SmartGen (HGM9530N)
- **Owner:** maintainer
- **Evidence:** HGM9530N protocol 1.0 p.14 "0140 Gen UAB LSB (*10)" / "0141 MSB (*10)"; p.15 "0180 Total Active Power Signed LSB (*10)" / "0181 Signed MSB (*10)". p.17 "0274-0275 Total Energy kWh 4Bytes" has no LSB/MSB mark.
- **Detail:** Mapped as wordOrder little (low-order word at the lower address), matching the labels and the HGM9510 document's worked example (0103 = E240H, 0104 = 0001H -> 123456). Total energy is left out. A one-off device read would settle it.

### `c09-smartgen-hgm9530n-sensors`: Engine sensor rows give no unit, scale or (for analogue sensors) sign.

- **Class 9, vendor:** SmartGen (HGM9530N)
- **Owner:** vendor
- **Evidence:** HGM9530N protocol 1.0 p.16: "0220 Temperature Sensor Value", "0222 Pressure Sensor Value", "0224 Fuel Level Sensor Value" (blank description); 0233-0243 "Signed, it is reserved if engine is not J-1939 engine." with no unit or scale.
- **Detail:** Coolant temperature and oil pressure (class core) are not mapped; the analogue rows also do not say which engine quantity the sensor measures.

### `c09-smartgen-hgm9530n-alarm-form`: The alarm data form gives 16 rows per offset without marking which row is bit 0.

- **Class 9, vendor:** SmartGen (HGM9530N)
- **Owner:** vendor
- **Evidence:** HGM9530N protocol 1.0 p.12, "0001-0015 Shutdown Alarm Area ... ALARM DATA FORM 30Bytes" (and six further areas to 0105); 5.4 Alarm data form, pp.20-25, "Offset Address 0000 Emergency Stop Alarm ... 0001 ECU Alarm". Register 0000 on p.12 marks its first row "(LSB)" and last "(MSB)"; the form has no such marks.
- **Detail:** Only register 0000 is mapped as flags. If SmartGen confirms the form uses the same order, map the shutdown and warning areas (e.g. 0001 + offset 0000).

### `c09-smartgen-hgm9510-blank-ratio`: Many value rows have a blank Ratio cell; NOTE1 defines only actual = received x ratio.

- **Class 9, vendor:** SmartGen (HGM9510)
- **Owner:** vendor
- **Evidence:** HGM9510 protocol 1.1, Table 6: "0084 Gen Freq Hz 16-bit Signed" (p.28), "0109-0110 Total Active Power kW 32-bit Signed" (p.29), "0141 Speed", "0142 Battery Volt V" (p.30), "0202 Accum. Start Times times", "0203-0204 Accum. Energy kWh" (p.32): Ratio blank. Mains Freq 0064 has 0.01 on the same table.
- **Detail:** A blank cannot be read as 1 (generator frequency in whole Hz is implausible next to mains frequency at 0.01 Hz). These rows, several of them class core, are not mapped. Ask SmartGen for the ratios.

### `c09-smartgen-hgm9510-note3-scope`: NOTE3 (32766 = no normal data) is attached to one row only.

- **Class 9, vendor:** SmartGen (HGM9510)
- **Owner:** vendor
- **Evidence:** HGM9510 protocol 1.1 p.42 NOTE3: "When the received data is 32766, it means no normal data"; the Remark "NOTE3" appears only on 0107 "C Phase Active Power" (p.29).
- **Detail:** Not applied as `invalid` to any mapped point. If it applies to all signed values, add invalid: [32766] to the 16-bit signed points (it cannot apply literally to 32-bit rows).

### `c09-smartgen-hgm9510-counter-sets`: The A and B counter sets (running time, starts, energy) are not explained.

- **Class 9, vendor:** SmartGen (HGM9510)
- **Owner:** vendor
- **Evidence:** HGM9510 protocol 1.1 p.35, rows 0270-0281 "A Running Hours" ... "B Gen Power kWh".
- **Detail:** "A Gen Power kWh" 0274-0275 is mapped as energy_counter_a (the only energy row with a ratio) with this caveat in its description.

### `c09-woodward-37528-signedness`: Manual 37528J states no data types or signedness for Protocol 5010 values.

- **Class 9, vendor:** Woodward (easYgen-3400, easYgen-3500)
- **Owner:** vendor
- **Evidence:** 37528J 9.2.3.1 Protocol 5010, pp. 701-739 (columns: Modicon, Start addr., Parameter ID, Description, Multiplier, Units). Scaling examples Tables 58-60 (pp. 405-406) say only "16 Bit, max. 32767".
- **Detail:** Non-negative quantities were mapped as u16; i16 only where a stated range includes negative values (exponents 3182/3183 "(2;1;0;-1)", "(0;-1)"; J1939 temperatures "-40 to 210 °C", p. 595). Total generator power 450011, reactive power 450012 and power factor 450013 were left out. B37574 (3000XT manual) declares the same rows int16, which suggests i16 but is a different product generation. Ask Woodward to confirm the types for 37528J.

### `c09-woodward-37528-long-word-order`: Manual 37528J gives no register order for the Long (32-bit) Protocol 5010 rows.

- **Class 9, vendor:** Woodward (easYgen-3400, easYgen-3500)
- **Owner:** vendor
- **Evidence:** 37528J p. 737-739, "AC Generator And Busbar Values (Long - 32 bits)" (e.g. 450323 Total gen. power, 450367 Gen. real energy 0,01 MWh, 450371 Gen. hours of operation 0,01 h).
- **Detail:** The only order statement in the manual is the CANopen transfer syntax (Tables 107-108, p. 593-594), which does not cover Modbus. 32-bit rows, including energy and operating hours, were left out. B37574 states big-endian with the high word first for the 3000XT; confirmation for the 3400/3500 would unlock these rows.

### `c09-woodward-37528-j1939-sentinels`: J1939 invalid sentinels are taken from the display table, matched by index.

- **Class 9, vendor:** Woodward (easYgen-3400, easYgen-3500)
- **Owner:** vendor
- **Evidence:** 37528J 7.5.1 "Standard visualization messages" pp. 595-596: Index 15308 / 15202 / 15205 with "Display with defective sensor" 32766 and "missing sensor" 32767 (resolution 1 rpm / 1 °C / 1 kPa); Protocol 5010 rows 450202, 450203, 450206 (multiplier 1).
- **Detail:** The manual does not say in the Modbus chapter that the register carries the same value. The extractor requires the resolution and unit to equal the 5010 multiplier and unit, and computes raw = display / multiplier. Engine stop information (450196) has its sentinels 65535/65279 stated in the 5010 row itself.

### `c09-woodward-b37574-scale-column`: B37574 does not define the Protocol 5010 "Scale" column ("*10", "*100", "*1000").

- **Class 9, vendor:** Woodward (easYgen-3200XT)
- **Owner:** vendor
- **Evidence:** B37574 9.2.4 Protocol 5010, e.g. 50009 Generator frequency Hz *100 (p. 987), 50052 Battery voltage V *10 (p. 990), 50366 Gen. real energy MWh *100 and 50370 Gen. hours of operation h *100 (p. 1023).
- **Detail:** Read as raw = value x N (exponent10 = -log10 N). 37528J corroborates it with multipliers 0.01 (450010 frequency), 0.1 (450053 battery) and 0,01 (450367 energy, 450371 hours), but that is a different manual. Ask Woodward to define the column.

### `c09-woodward-b37574-j1939-no-sentinels`: B37574 gives no raw "not available" values for J1939 measurements.

- **Class 9, vendor:** Woodward (easYgen-3200XT)
- **Owner:** vendor
- **Evidence:** B37574 Protocol 5010 rows 50201-50231 (p. 1019); the J1939 chapter (p. 904) says only that "Error" is displayed for a defective sensor and "Missing" for a missing sensor, without numeric values.
- **Detail:** The 3200XT contract has no invalid sentinels for J1939 coolant temperature and oil pressure. 37528J uses 32766/32767 for the 3400/3500; the 3000XT may do the same but the manual does not say so.

### `c10-imt-address-base`: Zero-based addressing is logically forced (the register list starts at 0) but never stated; please confirm.

- **Class 10, vendor:** IMT Technology (Si-RS485TC-T-MB, Si-RS485TC-2T-MB, Si-RS485TC-T-Tm-MB)
- **Owner:** maintainer
- **Decision:** D4
- **Evidence:** Modbus Specification Si-RS485…-MB p1 register table (register 0 = irradiance), p2 compatibility table (register 1). No worked request example. The Si-Sensor-RS485 instruction sheet, the Si-Modbus-Configurator documentation and the Si-Sensor data sheet do not state the base either.
- **Detail:** Evidence policy rule 3: register 0 cannot be a one-based number, so the numbers are PDU addresses. The extractor requires the lowest register to be 0, and info.description says the base is inferred. Confirm, or downgrade the three models to needs-check until a capture or vendor statement exists.

### `c10-imt-table`: The register list sits under the 0x03 and 0x04 entries of the function-code list; mapped as input registers.

- **Class 10, vendor:** IMT Technology (Si-RS485TC-T-MB, Si-RS485TC-2T-MB, Si-RS485TC-T-Tm-MB)
- **Owner:** maintainer
- **Evidence:** Modbus Specification Si-RS485…-MB p1 "Supported function codes" with "0x03: Read Holding Register" and "0x04: Read Input Register", then both register tables (p1, p2), then "0x08: Diagnostics" and "0x46: Communication Parameter" (p2). No sentence or frame example names the table; the companion IMT documents do not either.
- **Detail:** The extractor requires this structure (0x03, 0x04, the two tables, then 0x08 and 0x46) and maps the list as input registers, which FC 0x04 reads. This treats the structure as the statement that the list is what the read functions return. Confirm that 0x03 and 0x04 return the same registers, or downgrade the three models to needs-check if the structure is not accepted as a statement.

### `c10-kipp-float-word-order`: F32 registers (10006 onward) have no stated word order; left out.

- **Class 10, vendor:** Kipp & Zonen (SMP3, SMP6, SMP10)
- **Owner:** vendor
- **Evidence:** Communication Manual p3 rows 10006-10018 (FL_SENSOR1_DATA etc., F32); no MSB/LSB note. The SMP Series operational manual V2.0 does not state it either.
- **Detail:** Map the float registers once the vendor states the word order or a capture shows it.

### `c10-sr30-word-order`: SR30-M2-D1 manual never states which register of an S32/U32/Float value is the MSW.

- **Class 10, vendor:** Hukseflux (SR30-M2-D1)
- **Owner:** vendor
- **Evidence:** SR30-M2-D1 user manual v2508: register table rows 2+3 (S32 irradiance), 41+42 (Float); p56 "register 0x0002 and 0x0003 combined is a signed 32 bit integer"; p69 and p84 only say MSW and LSW must be read in one request. No MSW/LSW assignment and no worked example.
- **Detail:** The SR20-D2 manual states MSW first, but carrying that over would be a guess. A 16-bit-only contract was possible but would lack the core irradiance, so the model stays needs-check.

### `c10-sr20-model-string`: Sensor model string (registers 32-39) has no stated character order within a register; left out.

- **Class 10, vendor:** Hukseflux (SR20-D2)
- **Owner:** vendor
- **Evidence:** SR20-D2 manual v2404 p36 "String of 8 registers. This register will return 8 numbers, which correspond with ASCII characters."
- **Detail:** The SR15 manual's appendix example puts the first character in the low byte (byteOrder little), which suggests the SR20-D2 does the same, but this manual does not say so.

### `c10-apogee-shift-direction`: SP-722 integer registers are "shifted one/three decimal point(s) to the left"; the scale direction is ambiguous.

- **Class 10, vendor:** Apogee Instruments (SP-722)
- **Owner:** vendor
- **Evidence:** SP-722-SS manual p13 integer registers 44-48 and 51; the SP-422/SP-522 manuals say "(multiplied by 10)".
- **Detail:** Shifting the decimal point left divides, but the values are integer copies of floats, which implies multiplication. Left out until the vendor confirms the scale.

### `x-undefined-scale-marks`: Several register lists mark scaled values ("x10", "(*10)", "*100", "°C*10") without defining the direction of the factor.

- **Classes 5, 9, vendor:** Datakom, SmartGen, Woodward, Vaisala
- **Owner:** maintainer
- **Evidence:** c09-datakom-coeff-column (DKG COEFF column), c09-smartgen-scale-marks (HGM9510/HGM9530N), c09-woodward-b37574-scale-column (B37574 Protocol 5010), c05-opt100-scaled-int-notation (OPT100 Table 33).
- **Detail:** Class 9 maps these as register = value x N with multiplier 1/N, because the stated ranges and physical plausibility leave no other reading (for example "x100" on a 16-bit frequency). Each affected contract says so in info.description. Class 5 maps only unscaled OPT100 values, because "ppmv*0.1" reads either way. Confirm the class 9 reading, or move those models to needs-check.
- **Related:** `c09-datakom-coeff-column`, `c09-smartgen-scale-marks`, `c09-woodward-b37574-scale-column`, `c05-opt100-scaled-int-notation`

## Vendor errata

### `c01-cg-errata`: Part-code and Modicom/physical address mismatches in unselected rows.

- **Class 1, vendor:** Carlo Gavazzi (EM511, EM530, EM540)
- **Owner:** vendor
- **Evidence:** EM511 p.12 EM511DINAV81XS1SFA decimal 1795 vs hex 0702 (PFB's code); EM511 p.17 304360/110Bh (expected 1107h); EM511 p.21 and EM530-EM540 p.29 316657/4210h (expected 4110h); EM530-EM540 p.20 304357/1105h (expected 1104h) and 304360/110Bh; EM530-EM540 p.15 300282 0119h length 1 INT32 overlapping kvarh (-) TOT 0118h-0119h; EM511 p.22 Device state 'prevails on value 2' with no value 2 listed.
- **Detail:** Selected rows are all consistent; the SFA part code is left out of the identification enum.

### `c01-eastron-errata`: Typos in the SDM630 holding table and unit/revision inconsistencies.

- **Class 1, vendor:** Eastron (SDM230, SDM630)
- **Owner:** vendor
- **Evidence:** SDM630 p.6 hex bytes '00 OC' (40013) and '00 OE' (40015) use a letter O; p.7 Parameter Number column shows 30729 for 461457 and 464513 for 464513; p.3 30087 'Maximum total system power demand' unit VA (SDM230 p.3 says W); SDM230 page headers say V1.3, title says V1.4.
- **Detail:** The extractor accepts the letter O only in hex bytes it cross-checks against the 4X register number.

### `c02-janitza-19068-erratum`: Address 19068 is labelled "consumed, rate 1 [1]" in the German list but "consumed [0]" in the English UMG 96RM-E list.

- **Class 2, vendor:** Janitza electronics (UMG 96RM, UMG 96RM-PN)
- **Owner:** vendor
- **Evidence:** DE Dok. Nr. 1.040.033.u PDF p.17, 19068 "Real energy L1..L3, consumed, rate 1 [1]"; EN Dok. Nr. 1.040.085.8.o PDF p.19, 19068 "Real energy L1..L3, consumed [0]".
- **Detail:** Not used; import energy is taken from 5352 in "Energie, Typ Float" instead. Ask Janitza which label is right.

### `c02-siemens-bitmask-erratum`: Tables A-3 to A-5 give bit 1 the mask 0x00000010 (and higher bits 0x00000100, 0x00001000), which are nibble positions, not bit masks.

- **Class 2, vendor:** Siemens (SENTRON PAC3120, SENTRON PAC3220)
- **Owner:** vendor
- **Evidence:** PAC3120/PAC3220 manual PDF p.120 Table A-3 (offsets 207/209): DO 0.1 and DI 0.1, byte 3, bit 1, mask 0x00000010; PDF p.121 Tables A-4 and A-5 the same pattern. Table A-6 on PDF p.121 uses true bit masks.
- **Detail:** Matters once the digital I/O status is mapped; take the bit number, not the mask. Report to Siemens.

### `c03-solis-errata`: Several inconsistencies in protocol Ver3.7.

- **Class 3, vendor:** Solis (S6-GR1P4K, S6-GR1P5K, S6-GR1P6K)
- **Owner:** vendor
- **Evidence:** 6.11 'Set Reactive Power Percent' labels start address (3053) but sends 0B EA (3050); 6.13 'Set Active Power Percent' data 03 E8 (1000) labelled '10000, so 100%'; 5.1 3298 'Total PV current U16 0.1V' duplicates 3299; 3544 'MPPT 16 current U16 0.1V' duplicates 3545; 3049 unit 0.10% vs remark 10000<-->100%; 3043 refers to Appendix 3 but its values are in Appendix 2; SN example names 3061-3064 for rows 3060-3063.
- **Detail:** None of these rows is mapped. Report to Solis.

### `c04-fronius-chast-typo`: ChaSt value 3 is spelled DISCHAGING in the workbook.

- **Class 4, vendor:** Fronius (Symo GEN24 6.0 Plus, Symo GEN24 8.0 Plus, Symo GEN24 10.0 Plus)
- **Owner:** vendor
- **Evidence:** Complete Map row 242 and sheet storage (124) row 13, register 40355 ChaSt; the manual (Basic Storage Control Model) spells DISCHARGING.
- **Detail:** The extractor maps DISCHAGING to the enum name discharging through an explicit table.

### `c04-schneider-combox-example-erratum`: The ComBox map's worked example reads Battery Temperature at 0x009A as uint16, but its Table 3 lists uint32.

- **Class 4, vendor:** Schneider Electric
- **Owner:** vendor
- **Evidence:** 503-0253-01-01 Revision A.4 page 3 "Converting Data to Units of Measurement": "Modbus Address = 0x009A ... Data type = uint16 (one Modbus register)"; page 6 Table 3: "0x009A Battery Temperature uint32 r deg C 0.01 -273.0".
- **Detail:** Affects only the ComBox device map (not mapped here); relevant if the ComBox itself is added to the catalog.

### `c04-victron-doc-inconsistencies`: FAQ register range for vebus is stale and several uint16 Range cells say 0 to 65536.

- **Class 4, vendor:** Victron Energy (MultiPlus-II, Quattro, EasySolar-II GX)
- **Owner:** vendor
- **Evidence:** GX Modbus-TCP Manual section 2.3: com.victronenergy.vebus "3 to 60", while register list 3.81 has vebus rows up to address 205. Field list uint16 rows with Scalefactor 1, for example "Phase count" (28) and "VE.Bus state" (31), give Range "0 to 65536". The manual's mapping example says to divide by 10 "as specified in cell E3", but in register list 3.81 row 3 is com.victronenergy.system /Serial; the Input voltage phase 1 Scalefactor is cell E79.
- **Detail:** The extractor checks Range only on scaled rows, where it is consistent, and matches the mapping example by dbus path, not by cell. Report upstream.

### `c05-tapcon-230-avt-frequency-unit`: Frequency is given in "%" with range 0..1000 and multiplier 10.

- **Class 5, vendor:** Maschinenfabrik Reinhausen (TAPCON 230 AVT)
- **Owner:** vendor
- **Evidence:** Table 8 (p. 19), input register 11 "Frequency", Units "%".
- **Detail:** Almost certainly Hz. Not mapped (scaled row, see c05-reinhausen-multiplier-direction).

### `c05-tapcon-260-message-3-address`: Input "Message no. 3" is listed at address 17, out of sequence between 26 and 30.

- **Class 5, vendor:** Maschinenfabrik Reinhausen (260)
- **Owner:** vendor
- **Evidence:** Table 10 (p. 16): 25 Message no. 1, 26 Message no. 2, 17 Message no. 3, 30 Message no. 4.
- **Detail:** Not mapped. Confirm the real address on a device before adding it.

### `c05-tapcon-260-broadcast-address`: RS485, FOC and RJ45 settings say "0...254 (255 = Broadcast-Meldung)"; RS232 says "1...255 (0 = broadcast)".

- **Class 5, vendor:** Maschinenfabrik Reinhausen (260)
- **Owner:** vendor
- **Evidence:** Tables 3-6 (pp. 9-11).
- **Detail:** Modbus broadcast is address 0; the RS485/FOC/RJ45 rows look copied from another protocol and left in German. Recorded in device.unitId.notes.

### `c05-tapcon-250-tap-range`: Tap position range is "-50...140 (50L...140R)".

- **Class 5, vendor:** Maschinenfabrik Reinhausen (250)
- **Owner:** vendor
- **Evidence:** 6.3 Input registers (PDF p. 6), input 0.
- **Detail:** Mapped as i16 with the text in the description; the asymmetric range looks like a typo.

### `c05-tecsystem-t1048-table-errata`: The T1048 mapping table has a missing address and duplicated rows.

- **Class 5, vendor:** TECSYSTEM (T1048 with Modbus)
- **Owner:** vendor
- **Evidence:** p. 23: the "Ch3 temper. As (AL)" row (address 35 by sequence) has no address number; p. 25: the "CHANNELs 1÷4: Status" caption and rows 65-68 are printed twice; p. 24 repeats row 41.
- **Detail:** The extractor merges identical duplicates and fails on any conflicting duplicate; row 35 is not mapped.

### `c05-opt100-example-word-order`: The A.6 example bytes contradict the stated least-significant-word-first order.

- **Class 5, vendor:** Vaisala (OPT100)
- **Owner:** vendor
- **Evidence:** A.6 (p. 141): request 0x0016 (acetylene), response 0x40 0x40 "Value of first register (least significant word)", 0x00 0x00 "Value of second register (most significant word)", "Returned value 0x40400000". A.3 (p. 124) says the least significant 16 bits are at the listed register.
- **Detail:** With LSW first, words 0x4040, 0x0000 give 0x00004040, not 0x40400000. The contract follows A.3 (the MHT410 and MMT162 guides state the same order, and the MMT162 example agrees). The extractor pins this erratum, and test_value_u32 (expected 1234567890) is included so a device test can settle it.

### `c05-opt100-alarm-register-label`: Alarm register 305 names bit 15 "Any caution alert active in this register".

- **Class 5, vendor:** Vaisala (OPT100)
- **Owner:** vendor
- **Evidence:** Table 34 (p. 136), register 305 (0x0130) "Gas level alarms for present values".
- **Detail:** Copied from the caution registers. Not mapped (register 305 is the oxygen/nitrogen alarm field).

### `c06-abb-ssr1-bit-conflict`: The SSR1 device health bits differ between the 615 series protocol manuals and the RET615 ANSI point list.

- **Class 6, vendor:** ABB (REF615, REM615, RET615)
- **Owner:** vendor
- **Evidence:** 1MRS756468 rev. R table 18 (pdf page 45) and 1MAC057386-MB rev. A table 18 (pdf page 46): bit 0 "Device global warning", bit 1 "Device global error", bits 2-6 slot X130/X120/X110/X100/X000 warning or error. RET615 ANSI point list 1MAC203705-MB rev. B table 127 (pdf page 84): 128.00 "Device global error", 128.01 "Device global warning", 128.02-128.15 reserved. REF615 and REM615 list register 128 as "System status register 1 ... See Modbus CPM" (REF615 pdf page 19).
- **Detail:** Bits 0 and 1 are swapped and the slot bits are missing in the RET615 list. SSR1 is the 615 series device health word, so it is left out of all three contracts until ABB says which document is right. The first RET615 contract of this round mapped it from table 127; it was removed when the conflict was found.

### `c06-siemens-minmax-scaling-erratum`: The min/max chapter scaling header says "32768 corresponds to" and lists PF Min as 3.767.

- **Class 6, vendor:** Siemens (7SJ80, 7SK80, 7RW80)
- **Owner:** vendor
- **Evidence:** Chapter 1.6.6 Registers 40351 to 40520 (pdf pages 35-36) header "(32768 corresponds to ...)" versus "(32767 corresponds to ...)" in chapter 1.5; row 40461 "PF Min = Power Factor Minimum 3.767".
- **Detail:** Not mapped. The scaling of the min/max values cannot be stated exactly until Siemens confirms it.

### `c06-fanox-sil-a-map-errata`: SIL-A Rev. 05 lists address 636 for two state words, and its one-register map prints 724 without a description.

- **Class 6, vendor:** Fanox (SIL-A)
- **Owner:** vendor
- **Evidence:** Two-register states map: 636 is listed as SIGNALLING and again as Control LEDs. One-register map section 1.5.2, pdf page 37: "724 00 Trip" has no description (it is the LMS word 724/725). Data types (pdf page 6): "UINT32 2 Integer without sign of 16 bytes"; the general map uses LONG, which is not defined.
- **Detail:** The extractor keeps duplicates and refuses to select a shared address. It accepts the undescribed 724 only in the one-register map, which is used just for cross-checks. None of the selected points is affected.

### `c06-sepam-110f-erratum`: The measurement zone gives "I0 residual current (gain x 10)" the word address 110F instead of 110.

- **Class 6, vendor:** Schneider Electric (Sepam S20, Sepam T20, Sepam M20)
- **Owner:** vendor
- **Evidence:** PCRED301005EN/14 measurement zone, pdf page 113 (printed 111): rows 10D, 10E, 10F, then "110F", then 111.
- **Detail:** Not mapped (the contract uses the gain x 1 residual current at 109). The extractor rejects any selected row whose address is not three hex digits in table order, so the erratum cannot leak in.

### `c06-abb-scale-range-mismatch`: Some rows give scale 1 with a value range that has decimals, or a unit or name that does not fit.

- **Class 6, vendor:** ABB (REF615, REM615, RET615)
- **Owner:** vendor
- **Evidence:** REM615 147 "LD0.MPTTR1.TmpRl.mag i16 scale 1 Thermal level 0.00...9.99" (pdf page 17, while 149 has scale 10 for the same range). REF615 146 "T1PTTR1.Tmp.mag i16 scale 1 Protected object temperature -100.0...9999.9 [Celsius]" (pdf page 19). REM615 172.04/172.06 describe LoWrn as "Low alarm" and LoAlm as "Low warning" (pdf page 26). RET615 146 "T2PTTR1 .Tmp.mag i16 1 Object temperature -100.0…9999.9 [C]" and 147 ".TmpRl.mag u16 1 Relative temperature 0.00…99.99 [C]" (table 154, pdf page 97): scale 1 against decimals, and a temperature unit on a relative value. RET615 144 and 150 give ".SeqA.c2" for the zero-sequence amplitude, where REF615 has ".SeqA.c3" (tables 143, 159).
- **Detail:** The scale direction (register = value x scale) is now checked against the pinned protocol manuals, so it no longer rests on the value ranges. The RET615 contract follows the scale column and says that the temperature carries whole degrees. The REF615 and REM615 rows cited here are no longer mapped (c06-abb-default-offset); the REF615 and REM615 limit-supervision flags leave out the low warning/alarm bits 172.04/06. ABB should confirm whether the scale or the range is wrong. RET615 147 and the sequence rows are not mapped.

### `c07-brainboxes-errata`: The Brainboxes Modbus TCP manual swaps 3x/4x, and the ED-516 IEC 61131 range is short.

- **Class 7, vendor:** Brainboxes (ED-516, ED-538, ED-588)
- **Owner:** vendor
- **Evidence:** Using Modbus TCP with Brainboxes products, section 5: "'3x' referring to holding registers, and '4x' referring to input registers" (its own table maps 30001 to input registers and 40001 to holding registers). ED-516 "Read digital inputs / Coil" row: IEC 61131 "%M32 - 37" for 16 inputs (0x0020 - F, 00033 - 48), in both the PDF (section 9.2) and the HTML page.
- **Detail:** Neither affects the contracts (the logical and 984-style columns agree). Report to Brainboxes.

### `c07-moxa-errata`: A function-02 discrete input is marked R/W, and one start register uses 6-digit notation.

- **Class 7, vendor:** Moxa (ioLogik E1210, ioLogik E1212)
- **Owner:** vendor
- **Evidence:** Appendix A, E1210 and E1212 maps: DI_counterOverflowFlag 1000 / 02:INPUT STATUS / 11001 / R/W (PDF pp. 97, 100); E1210 deviceName start register "305041" where every other row, and the same row for the other models, uses 5 digits (35041) (PDF p. 97).
- **Detail:** The contracts map the overflow flag as a read-only discrete input; 305041 resolves to the same address 5040.

### `c07-icp-das-errata`: The 32-bit counter and frequency rows give the range as "0 to 4294967296".

- **Class 7, vendor:** ICP DAS (ET-2251)
- **Owner:** vendor
- **Evidence:** Section 6.3 3xxxx table, addresses 16 (0x10) and 64 (0x40) (PDF p. 180).
- **Detail:** The maximum of an unsigned 32-bit value is 4294967295. No effect on the contract.

### `c08-abb-fsca01-classic-table`: The Classic profile table prints 7-digit register references.

- **Class 8, vendor:** ABB (ACS580, ACH580, ACS880)
- **Owner:** vendor
- **Evidence:** FSCA-01 p. 74 prints "(4)000010", "(4)000011", "(4)000012" for DATA IN 1 to 3.
- **Detail:** Expected 6-digit (4)00010 to (4)00012; confirm with ABB before mapping.

### `c08-danfoss-fc300-example-values`: The Design Guide's worked examples do not match their raw values.

- **Class 8, vendor:** Danfoss (FC 301, FC 302)
- **Owner:** vendor
- **Evidence:** MG33BF02 PDF p. 188: raw 1352 "means ... 12.52%"; raw 11300 "means ... 1113.00".
- **Detail:** The examples cannot be used as scale evidence.

### `c08-danfoss-fc51-conversion-table`: The conversion table swaps the factors for indexes 2 and 1.

- **Class 8, vendor:** Danfoss (FC 51)
- **Owner:** vendor
- **Evidence:** MG.02.A4.02 p. 45 Table 6.1 lists index 2 -> 10 and index 1 -> 100.
- **Detail:** Indexes 0 to -5 are consistent with 10^index and are the only ones used; the extractor checks 0, -1, -2 and -3.

### `c08-automationdirect-igbt-format`: IGBT temperature is "16-bit unsigned" but has a negative range.

- **Class 8, vendor:** AutomationDirect (GS20, GS4)
- **Owner:** vendor
- **Evidence:** GS20 P06.43 (pp. 117 and 250) and GS4 P6.72 state "Format: 16-bit unsigned" with range -3276.7 to 3276.7 °C.
- **Detail:** Signedness cannot be resolved; left out.

### `c08-automationdirect-gs4-summary-dec`: The GS4 parameter summary prints a wrong 40001-based reference for P6.72 and P6.73.

- **Class 8, vendor:** AutomationDirect (GS4)
- **Owner:** vendor
- **Evidence:** GS4 p. 115 prints P6.72 hex 0648 with decimal 41608; the detail page 257 gives 41609 (40001 + 0x0648).
- **Detail:** Not used in the contract; reported for the vendor.

### `c09-datakom-32bit-word-order`: The manual states both register orders for 32-bit values.

- **Class 9, vendor:** Datakom (D-300, D-500, D-700)
- **Owner:** vendor
- **Evidence:** D-300 / 500 / 700 Modbus Application Manual V5.6, p.10 "Data types": "For data type longer than 16 bits, consecutive registers are used. The least significant register comes first." Same page, "Data formats": "32 bit variables ... The high order 16 bits are in the first register and the low order 16 bits are in the second register".
- **Detail:** No 32-bit row is mapped: generator phase voltages, currents and power (10240-10327), averages (10377-10383), counters (10616-10646: genset runs, cranks, engine hours run, energy). The class core run hours, start count and generator AC values are therefore missing. Ask Datakom which statement is right (or read a known counter on a device); the extractor raises if either sentence changes.

### `c09-datakom-11555-listed-three-times`: Address 11555 is listed three times with different meanings.

- **Class 9, vendor:** Datakom (D-300, D-500, D-700)
- **Owner:** vendor
- **Evidence:** V5.6 p.15: "11555 R 224 bit - These array of flags indicate activity status of various functions", "11555 R 32bit x10 Counter: mains total active energy (kWh)" and "11555 R 32bit x10 Counter: fuel counter".
- **Detail:** None of these rows is mapped. Ask Datakom for the correct addresses.

### `c09-smartgen-hgm9510-hours-range`: Accumulated running hours list the range 0~23.

- **Class 9, vendor:** SmartGen (HGM9510)
- **Owner:** vendor
- **Evidence:** HGM9510 protocol 1.1 p.32: "0199 Accum. Running Hours 0~23 1 h 16-bit Unsigned", followed by minutes and seconds 0~59; same for "A/B Running Hours" 0270 and 0276 (p.35).
- **Detail:** Mapped 0199 as running hours (h) with the stated range in the description; a total with no day register cannot be 0~23. Confirm with SmartGen.

### `c10-sr15-model-name-example`: SR15 appendix sensor-model example hex encodes "SR05-D1A3" while its ASCII row claims SR15-D2A2.

- **Class 10, vendor:** Hukseflux (SR15-D1A3)
- **Owner:** vendor
- **Evidence:** SR15 digital series user manual v2504, p74 appendix 9.12 sensor model string example.
- **Detail:** Report to the vendor.

### `c10-sr20-example-register`: The body temperature example requests register 6 but labels the response "Content of register 7".

- **Class 10, vendor:** Hukseflux (SR20-D2)
- **Owner:** vendor
- **Evidence:** SR20-D2 manual v2404 p42 "[00][06] = Start register" then "[08][B1] = Content of register 7" and "Temperature = Register 7 x 0.01".
- **Detail:** Register 6 is body temperature per Table 6.3.4; the contract follows the table.

### `c10-sr20-sign-bit-text`: Float appendix reasons "1098005873 < 2147483647 so sign bit = 1", which contradicts the positive result.

- **Class 10, vendor:** Hukseflux (SR20-D2)
- **Owner:** vendor
- **Evidence:** SR20-D2 manual v2404 p65 appendix 9.11.
- **Detail:** The decoded example value 15.14 is positive; the extractor checks the decode, not the reasoning text.

### `c10-sr30-hex-notation`: SR30 manual prefixes decimal register numbers with 0x and gives coil numbers that disagree with their decimal values.

- **Class 10, vendor:** Hukseflux (SR30-M2-D1)
- **Owner:** vendor
- **Evidence:** SR30-M2-D1 manual v2508 p56 "serial number in register 0x0040" (table: register 40); p57 "coil 0x0001 (decimal value 0)".
- **Detail:** Adds to the address-notation doubt for the SR30 beyond the missing word order.

### `c10-eko-ms60s-model-code`: MS-60S S-series row 0 gives no model code, while register 100 shows 0x0110 (the MS-80S code).

- **Class 10, vendor:** EKO Instruments (MS-60S)
- **Owner:** vendor
- **Evidence:** MS-60/MS-60S manual Ver. 5 p64 Table A4-9 row 0; p68 Table A4-15 register 100.
- **Detail:** model_code is mapped without an enum for MS-60S.

### `c10-kipp-naming`: Overview and detail tables disagree on names and defaults.

- **Class 10, vendor:** Kipp & Zonen (SMP3, SMP6, SMP10)
- **Owner:** vendor
- **Evidence:** Communication Manual overview tables p3-4 vs details p5-8: IO_UNDEFLOW_ERROR vs IO_UNDERFLOW_ERROR; IO_ROUND vs IO_ROUNDOFF; IO_FASTRESPONSE default 0 vs "ON"; IO_TRACKING_FILTER default 1 vs "OFF"; discrete footnote (1) vs (2); IO_STATUS_FLAGS refers to "U_STATUS_FLAGS"; demo C switch lacks break.
- **Detail:** The extractor maps IO_UNDEFLOW_ERROR to its detail row explicitly; no coil defaults are used.

### `c10-apogee-label-unit`: Register label "calibrated output watts" while the quantity is irradiance in W m-2.

- **Class 10, vendor:** Apogee Instruments (SP-422, SP-522)
- **Owner:** vendor
- **Evidence:** SP-422 manual p14 register 0-1 label; p5 and p7 specifications in W m-2.
- **Detail:** Unit W/m2 taken from the stated measurement unit; the extractor requires "W m-2" in the manual.

## Model scope

### `c02-abb-2x-naming`: The roster name "M4M 2X Modbus" does not occur in the map; product type 15 "M4M 2X RTU" was mapped.

- **Class 2, vendor:** ABB (M4M 2X Modbus)
- **Owner:** maintainer
- **Evidence:** 'Details' sheet IDs 15 to 20: M4M 2X RTU, RTU PQ1, RTU PQ2, RTU RTS, RTU PQ1+R, RTU PQ2+R. 'Mapping Table' column M names only "M4M 20 (all versions); M4M 30 (all versions)" even on rows whose ID columns include 15 to 26.
- **Detail:** Confirm that the roster means the plain RTU variant, or add contracts for the PQ/RTS variants.

### `c03-fronius-primo-scope`: Map applies only to Primo units with a Fronius Datamanager 2.0; DC input count not documented.

- **Class 3, vendor:** Fronius (Primo 3.0-1, Primo 4.0-1, Primo 5.0-1)
- **Owner:** maintainer
- **Evidence:** Primo instructions 030-15102024: Datamanager 2.0 'only available as an option', 'light version' without it. Workbook DCA/DCV remark: 'Not supported if multiple DC inputs'.
- **Detail:** Confirm with the Primo datasheet whether these models have one or two DC inputs. With two, dc_current and dc_voltage always read as not available and the per-input values live in model 160 (not mapped).

### `c03-solis-model-scope`: Protocol Ver3.7 does not name the S6-GR1P SKUs or firmware; scope is all power ranges, manufactured after mid-2023.

- **Class 3, vendor:** Solis (S6-GR1P4K, S6-GR1P5K, S6-GR1P6K)
- **Owner:** vendor
- **Evidence:** Solis RS485_MODBUS Ver3.7 page 4 sections 1 and 3; Appendix 1 page 18 single-phase types 0x1010/0x3F2 'For 0.7-8K1P/7-10K1P' and 0x1110 screen-less series.
- **Detail:** Mapped on the vendor's blanket statement. Ask Solis whether S6-GR1P4K/5K/6K built before mid-2023 use another protocol revision and which firmware applies; a client could check register 35000 once its address notation is confirmed.

### `c04-fronius-md-plus-name`: The Md example list names Symo GEN24 6.0/8.0/10.0 without "Plus".

- **Class 4, vendor:** Fronius (Symo GEN24 6.0 Plus, Symo GEN24 8.0 Plus, Symo GEN24 10.0 Plus)
- **Owner:** maintainer
- **Evidence:** Complete Map row 10, register 40021 Md, Range of values "e.g. ... Symo GEN24 6.0 Symo GEN24 8.0".
- **Detail:** Scope rests on the manual's link text "GEN24 Plus Modbus SunSpec Maps" and on the storage configuration. Confirm the Md string a Plus device reports before using Md for identification.

### `c04-schneider-sw4048-scope`: The Conext SW map Revision A.4 does not list a SW 4048 model.

- **Class 4, vendor:** Schneider Electric (Conext SW 4048 230)
- **Owner:** vendor
- **Evidence:** 503-0244-01-01 Revision A.4 (October 2015), page 2, Table 1 Applicable Products lists 865-2524, 865-2524-61, 865-4024, 865-4024-61 only.
- **Detail:** Find a newer SW map revision that names the SW 4048-230 (product ID needed), or vendor confirmation that the A.4 map applies.

### `c07-icp-das-et-2252-udio`: The ET-2252 has 16 universal DIO channels and the manual sizes its DI/DO rows only "Depend on the configuration".

- **Class 7, vendor:** ICP DAS (ET-2252)
- **Owner:** vendor
- **Evidence:** ET-2200 manual section 6.3.2 (PDF p. 178), row "(P)ET-2252 / 16 / Depend on the configuration".
- **Detail:** The nDI/nDO-sized rows cannot be given a fixed count. Options: map the 16-channel maximum per direction if ICP DAS confirms the addresses are fixed, or wait for repeat counts read from a register (reserved, spec section 11).

### `c08-abb-fsca01-scope`: FSCA-01 gives the addressing, but point meaning and scaling are in the drive firmware manuals.

- **Class 8, vendor:** ABB (ACS580, ACH580, ACS880)
- **Owner:** maintainer
- **Evidence:** FSCA-01 3AUA0000109533 Rev C: p. 12 lists compatible drives; pp. 35 and 74-77 give the profile words and the group/index formula. Parameter semantics are in the ACS580 (3AXD50000016097), ACH580 (3AXD50000027537) and ACS880 (3AUA0000085967) firmware manuals.
- **Detail:** Only status word, Act1 and Act2 are defined by FSCA-01 alone (3 points, below the minimum). Admit each firmware manual. A contract then needs the FSCA-01 formula (or the firmware manual's embedded fieldbus chapter, if it states its own) plus the firmware parameter table; see c08-multi-source-contracts.

### `c08-danfoss-fc300-programming-guide`: Parameter sizes and conversion indexes for FC 301/302 are in the Programming Guide, not fetched.

- **Class 8, vendor:** Danfoss (FC 301, FC 302)
- **Owner:** maintainer
- **Evidence:** MG33BF02 PDF p. 188: "consult the product relevant programming guide".
- **Detail:** Find and admit the FC 301/302 Programming Guide; then map with the resolved address base.

### `c09-datakom-unit-mode-d300`: Unit mode value 2 is documented for the D-500 and D-700 only.

- **Class 9, vendor:** Datakom (D-300)
- **Owner:** vendor
- **Evidence:** V5.6 p.14, register 10605 "Unit mode": "2= MANUAL mode (D700)", "2= RUN mode (D500)"; no D-300 entry.
- **Detail:** The D-300 contract leaves value 2 unnamed (unknown raw values are retained, spec 6.5) and says so in the point description. Confirm the D-300 meaning.

### `c09-deif-agc110-scope`: The document marks no generator AC measurements for AGC 110, so its contract has engine and status values only.

- **Class 9, vendor:** DEIF (AGC 110)
- **Owner:** vendor
- **Evidence:** 4189340442Z measurement table pp.43-53: the AGC 110 column is empty for 501-557 (generator voltages, frequencies, phase angles, currents, power, energy counters, run hours) and for 566 (start attempts); it is marked for 558-560, 567, 569-572, 576, multi-inputs 6-8, external analogue inputs, control register addresses and fan running hours 702-709. Alarm table: AGC 110 has engine alarms (1013 bits 9-15) and mode bits 0, 2, 3 of 1019, but also 1018 bit 13 "BB Hz/V OK" although no busbar measurement is marked for it. The document does not describe what an AGC 110 is.
- **Detail:** Mapped AGC 110 with the 7 points its column marks (no address is in doubt). Confirm with DEIF whether AGC 110 is an engine-only variant or whether the AC rows are missing marks; if they are missing, the AGC 111 rows would apply and the contract should be extended. Until then the contract lacks the class core voltages, currents, frequency, run hours and start count.

### `c09-woodward-b37574-model-column`: The 3100XT/3200XT manual's Protocol 5010 table marks rows for EG3500XT-P1/P2.

- **Class 9, vendor:** Woodward (easYgen-3200XT)
- **Owner:** maintainer
- **Evidence:** B37574 pp. 988-1023 Model column (e.g. 50024 Busbar 1 Voltage L2-L3 "EG3500XT-P2").
- **Detail:** The table is shared with the 3400XT/3500XT. Only rows marked "All" were mapped. The table does not distinguish 3100XT-P1 from 3200XT-P1, so the 3200XT contract could also serve the 3100XT-P1 if the roster wants it.

### `c10-sr15-d1a3-scope`: The SR15 digital series manual does not list SR15-D1A3 as a model.

- **Class 10, vendor:** Hukseflux (SR15-D1A3)
- **Owner:** maintainer
- **Evidence:** SR15 digital series user manual v2504 p12 Table 1.1.1 ordering codes SR15-D1 and SR15-D2A2; "SR15-D1A3" appears only in heading 5.12.1 (p40). D1A3 is an SR05 suffix (SR05-D1A3).
- **Detail:** Confirm the intended model (likely SR15-D1); then map it with the Hukseflux extractor.

## Source access

### `c01-socomec-cloudflare`: All Socomec communication tables sit behind a Cloudflare bot challenge.

- **Class 1, vendor:** Socomec (COUNTIS E23, COUNTIS E24, COUNTIS E43)
- **Owner:** vendor
- **Evidence:** 2026-11-13 from this machine: emea.socomec.com 2024-09/...E23..._2022-08_CMT_EN_0.html, 2024-09/...E24..._2017-08_CMT_EN_0.html, 2022-11/...E43..._2019-09_CMT201266_EN.html and 2025-01/...E43..._2025-01_CMT201266_EN.html: HTTP 403, cf-mitigated: challenge. Same 403 on www.socomec.co.in/.co.uk/.us/.fr/.de/.es/.it. www.socomec.com: HTTP 200 JavaScript SPA shell, not the document.
- **Detail:** Blocked under the admission rules (no challenge solving, no browser UA). Needs a vendor-hosted copy without the challenge (e.g. a PDF on a CDN or a repository mirror the vendor publishes). CI will re-test.

### `c01-eastron-bare-host-tls`: Roster URLs on eastroneurope.com fail TLS; www.eastroneurope.com works.

- **Class 1, vendor:** Eastron (SDM230, SDM630)
- **Owner:** tooling
- **Evidence:** curl exit 60: 'no alternative certificate subject name matches target host name eastroneurope.com'.
- **Detail:** Manifest uses the www host, as the SDM120 pilot does.

### `c02-eaton-access`: The IB150014EN register map PDF on eaton.com could not be fetched.

- **Class 2, vendor:** Eaton (Power Xpert Meter 4000, Power Xpert Meter 6000, Power Xpert Meter 8000)
- **Owner:** maintainer
- **Evidence:** curl exit code 92 (HTTP/2 stream INTERNAL_ERROR) on the pxm468k-modbus-register-map-ib150014en.pdf URL; --http1.1 timed out with 0 bytes; https://www.eaton.com/ failed the same way. No HTTP status was received.
- **Detail:** Retry from the clean CI runner. If eaton.com still refuses non-browser clients, find the same document on another Eaton-owned host, or ask Eaton. No contract until a pinned copy exists.

### `c03-sma-register-list`: SMA's per-product register lists are not reachable as a direct public URL.

- **Class 3, vendor:** SMA (SB3.0-1AV-41, SB5.0-1AV-41, STP5.0-3AV-40)
- **Owner:** maintainer
- **Evidence:** manuals.sma.de/SBxx-1AV-41/en-US/535578507.html names 'Parameters and Measured Values' and 'SMA MODBUS' without download links; sma.de product page has no Modbus download; files.sma.de needs the exact file name (guesses returned 404).
- **Detail:** Maintainer to find the direct files.sma.de URL for the SB/STP register list, then map the SMA profile.

### `c03-solaredge-cloudflare`: solaredge.com documents return a Cloudflare challenge (403).

- **Class 3, vendor:** SolarEdge (SE3000H-US, SE5000H-US, SE6000H-US)
- **Owner:** vendor
- **Evidence:** https://knowledge-center.solaredge.com/sites/kc/files/sunspec-implementation-technical-note.pdf -> 403, server cloudflare, 'Just a moment...'; www.solaredge.com copy and the HD-Wave datasheet also 403.
- **Detail:** Blocked for the corpus client; needs a vendor-hosted mirror without bot protection.

### `c03-schneider-akamai`: solar.se.com returns Akamai 'Access Denied' (403) for the register map and application note.

- **Class 3, vendor:** Schneider Electric (Conext CL 18000NA, Conext CL 25000NA, Conext CL 20000E)
- **Owner:** vendor
- **Evidence:** https://solar.se.com/eu/wp-content/uploads/sites/4/2021/11/Conext-CL_Modbus-Registers-Map_Rev1.5.pdf -> 403; /au/ copy 403; https://solar.se.com/eu/wp-content/uploads/sites/4/2021/11/App-Note_Using-Modbus-with-Conext-CL-Series_201501.pdf and /us/, /au/ copies 403; product page 403.
- **Detail:** Ask Schneider to publish map 503-0243-01-01 Rev 1.5 in the se.com download center (which works for this client, e.g. CL-60_Modbus-Registers-Map).

### `c04-schneider-roster-url-403`: solar.se.com returns 403 to the corpus client; download.se.com serves the same archive.

- **Class 4, vendor:** Schneider Electric (Conext SW 2524 230, Conext SW 4024 230, Conext SW 4048 230)
- **Owner:** maintainer
- **Evidence:** curl -A 'corpus-fetch/1' https://solar.se.com/us/wp-content/uploads/sites/7/2021/11/Conext-Modbus-Maps-V4.zip -> HTTP/2 403 with an Akamai x-reference-error header; the SW 230 V owner's guide on solar.se.com/eu -> 403 as well. https://www.se.com/us/en/download/document/Conext-Modbus-Maps-V4/ links https://download.se.com/files?p_Doc_Ref=Conext-Modbus-Maps-V4&p_enDocType=Application+Notes&p_File_Name=Conext-Modbus-Maps-V4.zip (HTTP 200, 1002899 bytes, identical sha256 on two fetches and through run.py).
- **Detail:** Update the roster link. A clean CI runner should re-test the download.se.com URL.

### `c04-sma-nda-terms`: The public SCS Modbus document is watermarked "internal use only - share under NDA" and forbids disclosure.

- **Class 4, vendor:** SMA (SCS-1900, SCS-2200, SCS-2475)
- **Owner:** maintainer
- **Evidence:** https://files.sma.de/downloads/MODBUS-SCS-NSD-xxx-TI-en-21.pdf (HTTP 200, 2974034 bytes, sha256 d9e00db53b2fc029a48ec4760a7ef54b780ced7fe1bdc7f20fab27dd87e2c308, stable). Watermark on each page; page 2 Legal Provisions: publication requires prior written approval; "utilization and disclosure of its contents are prohibited unless expressly authorized".
- **Detail:** Maintainer to decide whether register facts from this document may be published under MIT with attribution, or to ask SMA for written permission or a public edition. Technically mappable (base and byte order stated in sections 3.6.5-3.6.6; validity section 1.1 names the three models).

### `c05-qualitrol-vercel-403`: Every qualitrolcorp.com URL returns HTTP 403 "Forbidden" to corpus-fetch/1.

- **Class 5, vendor:** Qualitrol (509ITM, AKM345 Gen 3, T/Guard Link Rev B)
- **Owner:** vendor
- **Evidence:** 2026-11-13, all three roster PDFs (and the bare domain): HTTP/2 403, server Vercel, x-vercel-mitigated challenge (first fetches) and deny (re-check). The 59-byte bodies differ per response.
- **Detail:** The site applies Vercel bot mitigation; a credential-free client cannot pass it without solving a challenge, which the corpus does not do. Ask Qualitrol for a stable public download (or a mirror the vendor controls) and retry from a clean CI runner.

### `c05-tecsystem-url-rotation`: The roster PDF URLs return 404; the current manuals live at new img_<hash>.pdf URLs.

- **Class 5, vendor:** TECSYSTEM (NT935 AD, NT935 ETH, T1048 with Modbus)
- **Owner:** maintainer
- **Evidence:** https://tecsystem.it/docs/2026/img_619fbec9e3.pdf, /docs/2022/img_d4e67b92c2.pdf and /docs/2024/img_eee0ea6c8e.pdf redirect to www.tecsystem.it and return 404. The product pages link /docs/2026/img_a2c80980ca.pdf (NT935 AD), img_3c63f98b45.pdf (NT935 ETH) and img_99730cbd18.pdf (T1048), all republished in 2026.
- **Detail:** Each republication gets a new URL, so the lock will fail when TECSYSTEM next updates a manual. Expect to re-discover the URL from the product page, re-pin the checksum and re-review the mapping table.

### `c06-littelfuse-akamai-403`: Every Littelfuse URL returns HTTP 403 (Akamai "Access Denied") to the corpus-fetch/1 client.

- **Class 6, vendor:** Littelfuse (SE-330, MPU-32, FPU-32)
- **Owner:** maintainer
- **Evidence:** HTTP/2 403, server AkamaiGHost, for https://www.littelfuse.com/assetdocs/se-330-modbus-tcp-manual?assetguid=d6f77a91-332c-4008-acde-48a2b90167b6, .../mpu-32-manual?assetguid=20608747-e890-4d81-9ce4-0bce1331e769, .../fpu-32-manual?assetguid=49a6a295-2c32-45ae-9cfb-c1e82beff8cc and https://www.littelfuse.com/ (for example Reference #18.67c61102.1794608201.12e210b6), 2026-11-13.
- **Detail:** The assetdocs redirect could not be followed, so no direct PDF URL is known. Other Littelfuse hosts (such as origin-savvis.littelfuse.com) were deliberately not tried. Retry from a clean CI runner. If the block persists, ask Littelfuse for a public direct URL or treat the three relays as unavailable.

### `c08-rockwell-literature-403`: literature.rockwellautomation.com returns HTTP 403 to the corpus fetch client.

- **Class 8, vendor:** Rockwell Automation (PowerFlex 4, PowerFlex 40, PowerFlex 400)
- **Owner:** maintainer
- **Evidence:** GET of 22a-um001_-en-e.pdf, 22b-um001_-en-e.pdf and 22c-um001_-en-e.pdf with User-Agent corpus-fetch/1: HTTP 403, Server AkamaiGHost, Content-Length 479.
- **Detail:** Find a credential-free mirror on a Rockwell domain, or ask Rockwell for an allowed fetch path.

### `c09-deif-engine-values`: Oil pressure, coolant temperature and other engine-interface values are in a separate DEIF manual.

- **Class 9, vendor:** DEIF (AGC-3, AGC 110, AGC 111)
- **Owner:** maintainer
- **Evidence:** 4189340442Z p.55, measurement rows 593-641: "See H5/H7 manual or DRH" (marked X for all three); p.89, alarm registers 1020-1024 and 1026-1028: "See H5/H7 manual or DRH". The multi-input rows 580-585 are "scaled" / "unscaled" values without unit and depend on input configuration.
- **Detail:** Oil pressure and coolant temperature (class core) are not mapped. Admitting the DEIF option H5/H7 engine communication document as a second source would cover them; the multi-inputs cannot be mapped without a fixed unit and scale.

## Tooling

### `c01-tooling-pdf-columns`: sourcelib has no word-position helper; extractors infer table cells from pdftotext -layout columns.

- **Class 1, vendor:** Carlo Gavazzi; ABB (EM511, EM530, EM540, B21, B23, B24)
- **Owner:** tooling
- **Evidence:** corpus/extractors/carlo_gavazzi_em5xx_protocol.py rebuilds multi-line Notes cells by column position; abb_b2x_manual.py splits cells on runs of two spaces.
- **Detail:** A sourcelib pdf_words(data, page) helper on pdftotext -bbox-layout would make cell assignment explicit. Layout output may differ between Poppler versions (local 26.11.0; CI installs Ubuntu poppler-utils): the CI run is the real test. Also: run.py lets extractors return points, components and constraints but not defaults, so the parsed LSW-first word order is repeated on every Carlo Gavazzi i32 point.

### `c02-schneider-xls-reader`: The PM51xx/PM53xx register list is a legacy BIFF .xls with VBA macros, which sourcelib cannot read.

- **Class 2, vendor:** Schneider Electric (PM5110, PM5330)
- **Owner:** tooling
- **Evidence:** https://se.my.site.com/ckmContent/sfc/servlet.shepherd/document/download/069Kj00000TH2LXIA1, 902656 bytes, sha256 f2357b9d5eabda9ca3a087ade4a155fbac53eaaaf58063e09537fa4e694c7293, two identical fetches.
- **Detail:** Suggest a read-only BIFF8 cell reader in sourcelib (shared strings and number records only, never macros or formulas). No official PDF register list for PM5100/PM5300 was found; the firmware packages reportedly carry the list as well but were not fetched.

### `c03-html-article-text`: No sourcelib helper for HTML prose: section text lines, <br>-separated cell lines, list items.

- **Class 3, vendor:** Fronius (Primo 3.0-1, Primo 4.0-1, Primo 5.0-1)
- **Owner:** tooling
- **Evidence:** Fronius Datamanager manual: statements are <p> lines split by <br>; the Unavailable data records table pairs a <ul> cell with a <br>-separated value cell; sections are <article class=page title=...>. sourcelib.html_tables joins cell text and drops <br>.
- **Detail:** fronius_primo_sunspec_intsf._Manual implements this (skips <sup> footnote marks). A generic html_sections(data) in sourcelib would serve other evidence documents.

### `c03-layout-table-rows`: No sourcelib helper for pdftotext -layout table rows that wrap over several lines.

- **Class 3, vendor:** Solis (S6-GR1P4K, S6-GR1P5K, S6-GR1P6K)
- **Owner:** tooling
- **Evidence:** Solis page 7: '3004-30' + next line '05'; 'Energy today ... 0.1kW' + next line 'h'; 'AB line voltage / A phase' + 'voltage'.
- **Detail:** solis_grid_rs485_modbus.table_rows joins continuation lines by column. A generic column-aware row joiner in sourcelib would serve other PDF extractors.

### `c04-tooling-pdf-wrapped-cells`: Column-aware parsing of wrapped PDF table cells is implemented inside the extractor.

- **Class 4, vendor:** Schneider Electric (Conext SW 2524 230, Conext SW 4024 230)
- **Owner:** tooling
- **Evidence:** corpus/extractors/schneider_electric_conext_sw.py table_rows() joins name and notes continuation lines by start column and reports stray cells.
- **Detail:** Candidate sourcelib helper (pdf_layout_rows) together with a shared label-to-identifier slug helper used by the Conext and Victron extractors.

### `c05-tooling-column-helpers`: Column-aware PDF helpers were written inside the class-05 extractors; candidates for sourcelib.

- **Class 5, vendor:**
- **Owner:** tooling
- **Evidence:** corpus/extractors/vaisala_modbus_reference.py (cells, fragment_at), reinhausen_tapcon_modbus.py (first_cell, subsequence, dehyphenate), tecsystem_mapping_table.py (bit_table assigns cells to the nearest "BIT n" header, header_block, table_rows with duplicate merge).
- **Detail:** pdftotext -layout interleaves wrapped cells across rows; every extractor needed "cell at column x" and "bit table by header centre" helpers. A shared, tested version in sourcelib.py would cut duplication. Not added here because sourcelib.py is off limits for class agents.

### `c06-sourcelib-pdf-word-boxes`: sourcelib has no word-box PDF helper; the Sepam extractor carries its own pdftotext -bbox reader.

- **Class 6, vendor:** Schneider Electric (Sepam S20, Sepam T20, Sepam M20)
- **Owner:** tooling
- **Evidence:** corpus/extractors/schneider_electric_sepam_series20.py pdf_words(): the per-application b/v marks in the selection table (pdf page 15) and the TS tables (pdf pages 116-117) only line up with their column by x position. corpus/extractors/deif_ml2_h2_h9.py carries a similar bbox_pages() helper.
- **Detail:** Add a sourcelib.pdf_words(data, first, last) returning (x0, y0, x1, y1, text) per page, with the same subprocess limits as pdf_pages. Then both extractors can drop their copies.

### `c06-corpus-variants`: Configuration-dependent points cannot be expressed as variants because extractor results carry no variants.

- **Class 6, vendor:** ABB (REF615, RET615, Sepam S20, Sepam T20, Sepam M20)
- **Owner:** tooling
- **Decision:** D3
- **Evidence:** REF615 point list: "Frequently updated registers, variants FE05,06" (voltage_a_n 152, active power 161), "Frequency metering, Energization state (FE08)" (168), pdf pages 19-20. Indication 199.00 is listed for both FE08 (SECRSYN1.SynPrg) and FE01-07 (XGGIO130.Ind1). Sepam measurement zone note: "Only the measurements related to the Sepam function are significant. The values of the others are zero" (pdf page 113). RET615 table 2 (pdf pages 23-25) lists VMMXU, RESVMMXU, VSMSQI, PEMMXU, SPEMMXU and FMMXU for configuration F (TA06) only, so the RET615 contract leaves out voltages, power and frequency.
- **Detail:** build_contract() accepts only points, components and constraints, so §5.6 variants cannot be emitted. The REF615 contract notes the configuration per point (now the CB condition monitoring flags, FE02,04,05,06), and Sepam is split into one contract per application. Supporting variants in the corpus would let one REF615 contract select configuration-specific points, and would allow the overlapping 199.00 rows, which only a variant can separate. RET615 leaves out its configuration-F-only measurands for the same reason.

### `c07-sourcelib-layout-helpers`: Three parsing helpers written in class 07 extractors could move to sourcelib.

- **Class 7, vendor:** ICP DAS (ET-2251, ET-2268, SIO-MB08THMS, ED-538, ED-588)
- **Owner:** tooling
- **Evidence:** icp_das_et2200_dio.assign_lines (nearest-centre grouping of wrapped pdftotext -layout table cells, with a mirror tie-break); automationdirect_stride_sio.left_column (drop a right-hand column printed next to a bit diagram); brainboxes_ed_tables.span (abbreviated ranges such as "0x0400 - 3", "11025 - 8").
- **Detail:** Candidates for shared helpers once a second vendor needs them.

### `c08-multi-source-contracts`: run.py builds one contract from one source; adapter-plus-drive manuals need two.

- **Class 8, vendor:** ABB (ACS580, ACH580, ACS880)
- **Owner:** tooling
- **Evidence:** corpus/run.py contract entries take a single source; FSCA-01 addressing plus firmware manual parameters.
- **Detail:** Consider letting one contract cite a second pinned source (addressing evidence) in run.py.

### `c08-sourcelib-pdf-control-chars`: pdf_pages text contains BEL (0x07) characters inside words.

- **Class 8, vendor:** AutomationDirect (GS4)
- **Owner:** tooling
- **Evidence:** GS4 pp. 312-313 extract with BEL characters, for example "0: <BEL>No Error" and "I<BEL>GBT".
- **Detail:** automationdirect_durapulse_status.py strips them locally (clean()). Suggest an option in sourcelib.pdf_pages that removes C0 control characters other than tab, newline and form feed.

### `c09-deif-pdf-word-boxes`: Add a word-box PDF helper to sourcelib for tables with rotated column headers.

- **Class 9, vendor:** DEIF (AGC-3, AGC 110, AGC 111)
- **Owner:** tooling
- **Evidence:** corpus/extractors/deif_ml2_h2_h9.py bbox_pages(): runs pdftotext -bbox-layout and parses <word> boxes, because pdftotext -layout cannot attribute "X" marks to the rotated product columns of the DEIF tables.
- **Detail:** Suggest sourcelib.pdf_words(data, first, last) returning (x0, y0, x1, y1, text) per page, using stdin like pdf_pages(). Product-matrix tables (one "X" column per model) are common in multi-product vendor manuals.

### `c09-smartgen-pdf-raw-text`: Add a raw (content-order) text mode to sourcelib.pdf_pages.

- **Class 9, vendor:** SmartGen (HGM9510)
- **Owner:** tooling
- **Evidence:** corpus/extractors/smartgen_hgm9510.py raw_pages(): runs `pdftotext -raw`, because in -layout mode the HGM9510 table cells wrap over three lines around the address line and in the default mode the columns are separated.
- **Detail:** Suggest pdf_pages(data, first, last, mode="layout"\|"raw"\|"plain"), keeping stdin input as now.

### `c10-extractor-variants`: corpus/run.py accepts only points, components and constraints from an extractor, so variants cannot be emitted.

- **Class 10, vendor:** EKO Instruments (MS-40S, MS-60S, MS-80S)
- **Owner:** tooling
- **Evidence:** corpus/run.py build_contract, "Unexpected extractor result keys".
- **Detail:** Needed if configuration- or firmware-dependent maps (EKO register types, IMT firmware ranges) are to be modelled.

### `c10-pdf-table-helpers`: Suggest shared sourcelib helpers for column splitting by header positions and framed multi-register PDF rows.

- **Class 10, vendor:** Hukseflux (SR20-D2)
- **Owner:** tooling
- **Evidence:** corpus/extractors/hukseflux_sr_digital.py table_rows, eko_instruments_ms_s_series.py wide_rows, apogee_instruments_sp_modbus.py float_rows/integer_rows each implement it locally.
- **Detail:** A sourcelib helper would cut repeated layout parsing.

### `x-sourcelib-pdf-tables`: Extractors carry their own PDF table parsing (layout columns, wrapped rows, word boxes, raw text order); sourcelib has none of it.

- **Classes 1, 3, 4, 5, 6, 7, 9, 10, vendor:** several
- **Owner:** tooling
- **Evidence:** c01-tooling-pdf-columns, c03-layout-table-rows, c04-tooling-pdf-wrapped-cells, c05-tooling-column-helpers, c06-sourcelib-pdf-word-boxes, c07-sourcelib-layout-helpers, c09-deif-pdf-word-boxes, c09-smartgen-pdf-raw-text, c10-pdf-table-helpers.
- **Detail:** Move the shared patterns (column split by header positions, wrapped-cell joining, pdftotext -bbox word boxes, raw mode) into sourcelib once two extractors use the same one, and keep extractor output byte-identical.
- **Related:** `c01-tooling-pdf-columns`, `c03-layout-table-rows`, `c04-tooling-pdf-wrapped-cells`, `c05-tooling-column-helpers`, `c06-sourcelib-pdf-word-boxes`, `c07-sourcelib-layout-helpers`, `c09-deif-pdf-word-boxes`, `c09-smartgen-pdf-raw-text`, `c10-pdf-table-helpers`

### `x-poppler-layout-version`: Most PDF extractors parse pdftotext -layout text, whose spacing and glyph order change between Poppler versions; CI uses the runner image's poppler-utils.

- **Classes 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, vendor:** several
- **Owner:** tooling
- **Evidence:** DURApulse GS4 p. 312 (2100h error codes): Poppler 26.11 gives "91~98: <BEL>reserved", Ubuntu 24.04's Poppler 24.02 gives "r<BEL> eserved" and "U<BEL> phase", so the first CI run of the full corpus failed on this source only.
- **Detail:** The GS4 error-code list now reads pdftotext -bbox word boxes, joining touching boxes, and gives identical output on both versions. All 61 sources verify on Ubuntu 24.04 (Python 3.12, Poppler 24.02) and locally (Python 3.15, Poppler 26.11). An ubuntu-latest image upgrade can still change the layout text: pin the corpus jobs to ubuntu-24.04, or move layout-sensitive tables to word boxes in sourcelib.
- **Related:** `c08-sourcelib-pdf-control-chars`, `x-sourcelib-pdf-tables`

### `x-extractor-variants`: run.py builds one variant-free contract from one source; configuration-dependent layouts and adapter-plus-drive manuals cannot be generated.

- **Classes 6, 8, 10, vendor:** several
- **Owner:** tooling
- **Evidence:** c06-corpus-variants, c10-extractor-variants, c08-multi-source-contracts.
- **Detail:** Let an extractor return variants, and let a contract name several sources, once the draft's variants.match covers configuration (see the configuration theme).
- **Related:** `c06-corpus-variants`, `c10-extractor-variants`, `c08-multi-source-contracts`
