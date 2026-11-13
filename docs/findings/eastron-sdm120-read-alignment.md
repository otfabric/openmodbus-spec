# Eastron SDM120-Modbus read alignment

The [Eastron protocol v2.4](https://www.eastroneurope.com/images/uploads/products/protocol/SDM120-MODBUS_Protocol.pdf)
requires even start addresses and even register counts for FC 04 (PDF page 3)
and FC 03 (PDF page 4). Its input table on page 5 identifies each value as a
two-register float. The [pilot contract](../../devices/eastron/sdm120-modbus/telemetry.omb.yaml)
uses that width and the zero-based addresses from the table.

The draft can express the width of each point and an upper request limit.
It lacks a device-level alignment constraint. A planner can satisfy the
current request-size limit and still ask for an odd-sized or misaligned range.

For D10, consider optional start-address and register-count multiples per
read table. For this device both multiples would be 2. A start of 0 with
count 2 is aligned. A start of 1 with count 2 or a start of 0 with count 3
should be rejected. A validator would check explicit blocks against these
multiples. A runtime would apply the same rule to merged requests, alongside
the existing range policies. This proposal leaves the draft schema as-is.
