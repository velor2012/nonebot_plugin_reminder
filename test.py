import re

pattern = r'^(?:(\@.*))*定时[\s]*列表(\d+)?'  # 匹配一个或多个数字

text = "@dsafsa定时列表"

result = re.findall(pattern, text)
print(result)  # 输出: ['123', '456']