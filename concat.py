import os
import pandas as pd

path = './data/'

files = os.listdir(path)
dfs = []
count = 1
for file in files:
    if not os.path.isdir(file):
        print('正在处理第%d个文件' % count)
        file_path = path + '/' + file
        df = pd.read_excel(file_path)
        dfs.append(df)
        count += 1

df = pd.concat(dfs, ignore_index=True)
df.to_excel('data.xlsx')
