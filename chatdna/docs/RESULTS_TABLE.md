| Run | Device | Steps | Predicted tokens | Seconds | Tokens/s | Final val NLL | Test NLL | Peak allocated GiB |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| A1 | GPU | 100 | 3,899 | 200.05 | 19.49 | 5.2094 | 5.5608 | 1.353 |
| A1 conservative | GPU | 100 | 3,899 | 168.65 | 23.12 | 5.7206 | 5.9783 | 1.353 |
| B1 | CPU | 200 | 15,781 | 69.93 | 225.68 | 6.9082 | 7.2129 | 0.000 |
| B1 longer | GPU | 2,000 | 166,249 | 64.19 | 2589.75 | 6.3260 | 6.6768 | 0.125 |
