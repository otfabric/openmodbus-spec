# Eastron SDM120-Modbus read alignment

The [Eastron protocol v2.4](https://www.eastroneurope.com/images/uploads/products/protocol/SDM120-MODBUS_Protocol.pdf)
requires even start addresses and even register counts for FC 04 (PDF page 3)
and FC 03 (PDF page 4). Its input table on page 5 identifies each value as a
two-register float. The [pilot contract](../../devices/eastron/sdm120-modbus/telemetry.omb.yaml)
uses that width and the zero-based addresses from the table.

The mapped voltage point starts at 0 and occupies registers 0 and 1.
A read of that point starts at 0 with count 2. Starting at 1 splits the
point. The two-register width already supplies the boundary a point-based
planner needs.

For this mapping, merging adjacent complete points with the default
`gaps: forbid` preserves the vendor's pair boundaries. For example, the
frequency and import-energy points at 70 and 72 can be read together
with count 4. This case supplies a read-planner regression using the
existing contract fields.
