# eval 包标记（2026-11-10 补）
#
# 目的：让 `python -m unittest discover -s eval/tests -t .` 能发现用例。
# 此前 eval/ 与 eval/tests/ 均无 __init__.py，discover 会报
#   ImportError: Start directory is not importable
# 只能退化为逐个模块点名跑（`python -m unittest eval.tests.test_xxx`）。
#
# 注意：各测试文件内部用 sys.path.insert(ROOT/"eval") + `import verify_claims`
# 的路径注入方式导入被测模块，不依赖包相对导入，因此加本文件不影响原跑法。
