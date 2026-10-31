| protocol   | policy   | anchoring   |   batch |   tx_per_year |   ledger_gb_per_year |   ledger_reduction |   proof_bytes |   merkle_cpu_us_per_batch |   verify_cpu_us |
|:-----------|:---------|:------------|--------:|--------------:|---------------------:|-------------------:|--------------:|--------------------------:|----------------:|
| tree_local | every_1  | per-record  |       1 |      1.46e+04 |              0.08871 |             0      |             0 |                    0.2479 |          0.0571 |
| tree_local | every_1  | per-event   |       5 |   2920        |              0.01774 |             0.8    |            96 |                    6.02   |          1.184  |
| tree_cap   | every_1  | per-record  |       1 |      1.46e+04 |              0.08871 |             0      |             0 |                    0.2479 |          0.0571 |
| tree_cap   | every_1  | per-event   |       5 |   2920        |              0.01774 |             0.8    |            96 |                    6.02   |          1.184  |
| mlp_local  | every_1  | per-record  |       1 |      1.46e+04 |              0.08871 |             0      |             0 |                    0.2479 |          0.0571 |
| mlp_local  | every_1  | per-event   |       5 |   2920        |              0.01774 |             0.8    |            96 |                    6.02   |          1.184  |
| fedavg     | every_1  | per-record  |       1 |      8.76e+04 |              0.5323  |             0      |             0 |                    0.2479 |          0.0571 |
| fedavg     | every_1  | per-round   |       6 |      1.46e+04 |              0.08871 |             0.8333 |            96 |                    6.135  |          1.182  |
| fedavg     | every_1  | per-event   |      30 |   2920        |              0.01774 |             0.9667 |           160 |                   24.83   |          1.91   |
| lpra       | every_1  | per-record  |       1 |      8.76e+04 |              0.5323  |             0      |             0 |                    0.2479 |          0.0571 |
| lpra       | every_1  | per-round   |       6 |      1.46e+04 |              0.08871 |             0.8333 |            96 |                    6.135  |          1.182  |
| lpra       | every_1  | per-event   |      30 |   2920        |              0.01774 |             0.9667 |           160 |                   24.83   |          1.91   |
| central    | every_1  | per-record  |       1 |   2920        |              0.01774 |             0      |             0 |                    0.2479 |          0.0571 |
| central    | every_1  | per-event   |       1 |   2920        |              0.01774 |             0      |             0 |                    0.2479 |          0.0571 |