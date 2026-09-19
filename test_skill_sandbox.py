from core.security.skill_sandbox import validate_skill_code

# OK
print(validate_skill_code("import json\nprint(json.dumps({'a': 1}))"))
print(validate_skill_code("x = 1 + 1"))

# KO
print(validate_skill_code("import subprocess"))
print(validate_skill_code("from os import system"))
print(validate_skill_code("eval('1+1')"))
print(validate_skill_code("x = ().__class__.__bases__"))
print(validate_skill_code("from . import evil"))