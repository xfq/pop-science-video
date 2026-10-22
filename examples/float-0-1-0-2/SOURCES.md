# SOURCES

访问日期均为 2026-10-21。`facts.json` 是机器可读的版本。

| id | 主张 | 类型 | 来源 | 链接 | 核验 |
| --- | --- | --- | --- | --- | --- |
| c1 | 0.1 + 0.2 = 0.30000000000000004；Python/JS/C/Java 一致 | 官方文档 + 标准 | Python Tutorial; IEEE 754-2019 | https://docs.python.org/3/tutorial/floatingpoint.html · https://standards.ieee.org/ieee/754/6210/ | 四语言实机运行 |
| c2 | 0.1 无法用有限二进制小数精确表示 | 论文 + 官方文档 | Goldberg 1991; Python Tutorial | https://dl.acm.org/doi/10.1145/103162.103163 · https://docs.python.org/3/tutorial/floatingpoint.html | 精确十进制展开 |
| c3 | binary64 = 1 + 11 + 52 位，有效数字 53 位 | 标准 | IEEE 754-2019 | https://standards.ieee.org/ieee/754/6210/ | 字段核对 |
| c4 | 0.1 的二进制展开以 0011 循环 | 论文 | Goldberg 1991 | https://dl.acm.org/doi/10.1145/103162.103163 | 长除法推导 |
| c5 | `(0.1).hex()` = `0x1.999999999999ap-4` | 官方文档 | Python `float.hex` | https://docs.python.org/3/library/stdtypes.html#float.hex | 实机运行 |
| c6 | `math.isclose` 默认 `rel_tol=1e-09` | 官方文档 | Python `math.isclose` | https://docs.python.org/3/library/math.html#math.isclose | 文档 + 实机 |
| c7 | 与 0.3 的差约 1 ulp | 标准 | IEEE 754-2019 | https://standards.ieee.org/ieee/754/6210/ | 实机减法 + 间距计算 |
| c8 | 默认精度下 Decimal 三值相等 | 官方文档 | Python `decimal` | https://docs.python.org/3/library/decimal.html | 实机运行 |
| c9 | 默认 binary64 的跨语言一致性 | 标准 | IEEE 754-2019 | https://standards.ieee.org/ieee/754/6210/ | 四语言实机运行 |
| c10 | 53 位 ≈ 15–17 位十进制 | 官方文档 | Python Tutorial | https://docs.python.org/3/tutorial/floatingpoint.html | log10 计算 + 文档 |

## 没有采用的说法

- “浮点数就是不准”：不准确。可表示的值是精确的；不精确的是十进制输入和运算结果的舍入。
- “这是 Python 的 bug”：不成立。这是 IEEE 754 binary64 的默认行为。
- “用 Decimal 就无限精确”：不成立。Decimal 仍然有上下文精度。
- “0.1 + 0.2 的结果是随机的”：不成立。舍入是确定性的，且默认 ties-to-even。

## 实机核验

完整命令与输出见 `evidence/verification.txt`。核验环境：macOS arm64，Python 3.14.6，Node v24.19.0，Apple clang，OpenJDK。
