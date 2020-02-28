# -*- coding: UTF-8 -*-
import os
import json
import time
import rsa
import base64
import urllib
import binascii
import traceback
import requests
import pandas as pd
from lxml import etree
from datetime import datetime


class NoResultException(Exception):

    def __init__(self):
        super().__init__()

    def __str__(self):
        return 'No result'


class Config(object):
    def __init__(self, **entries):
        self.__dict__.update(entries)


class WeiboSpider(object):
    def __init__(self, config):
        self.year = config.year
        self.month = config.month
        self.day = config.day
        self.query = config.query
        self.config = config
        self.weibo = list()
        self.cookie = self.get_cookie()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:54.0) Gecko/20100101 Firefox/54.0'
        }

    def get_cookie(self):
        data = {
            'entry': 'weibo',
            'gateway': '1',
            'from': '',
            'savestate': '7',
            'qrcode_flag': 'false',
            'useticket': '1',
            'pagerefer': 'https://login.sina.com.cn/crossdomain2.php?action=logout&r=https%3A%2F%2Fweibo.com%2Flogout.php%3Fbackurl%3D%252F',
            'wsseretry': 'servertime_error',
            'vsnf': '1',
            'su': '',
            'service': 'miniblog',
            'servertime': '1529058370',
            'nonce': 'CPEDL5',
            'pwencode': 'rsa2',
            'rsakv': '1330428213',
            'sp': '',
            'sr': '1536*864',
            'encoding': 'UTF-8',
            'prelt': '75',
            'url': 'https://weibo.com/ajaxlogin.php?framelogin=1&callback=parent.sinaSSOController.feedBackUrlCallBack',
            'returntype': 'META'
        }
        username = self.config.username
        password = self.config.password
        pre_url = "http://login.sina.com.cn/sso/prelogin.php?entry=weibo&callback=sinaSSOController.preloginCallBack&su=emhlZGFwYXQlNDAxNjMuY29t&rsakt=mod&client=ssologi"
        s = requests.session()
        res = s.get(pre_url)
        res = res.text.split('(')[-1].split(')')[0]
        pre_json = json.loads(res)
        servertime = pre_json['servertime']
        nonce = pre_json['nonce']
        rsakv = pre_json['rsakv']
        pubkey = pre_json['pubkey']
        su = base64.encodestring(urllib.parse.quote(
            username).encode(encoding="utf-8"))[:-1]
        # rsa2计算sp
        rsaPubkey = int(pubkey, 16)
        key = rsa.PublicKey(rsaPubkey, 65537)
        message = str(servertime) + '\t' + str(nonce) + '\n' + str(password)
        sp = rsa.encrypt(message.encode(encoding="utf-8"), key)
        sp = binascii.b2a_hex(sp)
        data['servertime'] = servertime
        data['nonce'] = nonce
        data['rsakv'] = rsakv
        data['su'] = su
        data['sp'] = sp

        url = 'http://login.sina.com.cn/sso/login.php?client=ssologin.js(v1.4.18)&wsseretry=servertime_error'
        res = requests.post(url, data=data)
        cookie = res.cookies.get_dict()
        return cookie

    def set_encoding(self, res):
        '''
        解决weibo网页不同编码问题
        '''
        code = ['UTF-8', 'GBK']
        for item in code:
            if item in res.text:
                res.encoding = item
                break

    def extract_digit(self, s):
        if s:
            return ''.join([x for x in s if x.isdigit()])
        else:
            return ''

    def get_detail_info(self, url, weibo):
        res = requests.get(url, headers=self.headers, cookies=self.cookie)
        res.encoding = 'utf-8'
        html = res.text
        lines = html.splitlines()  # splitlines将字符串按照\n切割
        weibo['gender'] = ''
        weibo['location'] = ''
        weibo['age'] = ''
        for line in lines:
            line = line.replace(r'\t', '')
            line = line.replace(r'\n', '')
            line = line.replace(r'\r', '')
            if line.startswith('<script>FM.view({"ns":"pl.header.head.index","domid":"Pl_Official_Headerv6__1"'):
                n = line.find('html":"')
                if n > 0:
                    line = line[n + 7: -12].replace("\\", "")  # 去掉所有的斜杠
                    if not line.find('<div class="search_noresult">') > 0:
                        parser = etree.HTML(line)
                        temp = parser.xpath(
                            '//*[@class="pf_username"]/span/a/i/@class')[0].split(' ')[1]
                        if temp == 'icon_pf_male':
                            weibo['gender'] = '男'
                        elif temp == 'icon_pf_female':
                            weibo['gender'] = '女'
            if line.startswith('<script>FM.view({"ns":"pl.content.homeFeed.index","domid":"Pl_Core_UserInfo'):
                n = line.find('html":"')
                if n > 0:
                    line = line[n + 7: -12].replace("\\", "")  # 去掉所有的斜杠
                    if not line.find('<div class="search_noresult">') > 0:
                        parser = etree.HTML(line)
                        # lv = parser.cssselect(
                        #     '.W_icon_level > span')
                        # lv = lv[0].text[3:] if len(lv) > 0 else ''
                        # weibo['lv'] = lv  # 等级
                        t = 1
                        flag1 = False
                        flag2 = False
                        while True:
                            try:
                                icon = parser.xpath(
                                    '//*[@class="WB_innerwrap"]/div/div/ul/li[{}]/span[1]/em/@class'.format(t))[0].split(' ')[1]
                                if icon == 'ficon_cd_place':
                                    flag1 = True
                                    weibo['location'] = parser.xpath(
                                        '//*[@class="WB_innerwrap"]/div/div/ul/li[{}]/span[2]'.format(t))[0].xpath('string(.)').strip()
                                elif icon == 'ficon_constellation':
                                    flag2 = True
                                    age_text = parser.xpath(
                                        '//*[@class="WB_innerwrap"]/div/div/ul/li[{}]/span[2]'.format(t))[0].xpath('string(.)').strip()
                                    y = age_text.split('年')[0]
                                    if y.isdigit():
                                        weibo['age'] = datetime.now().year - int(y)
                                    else:
                                        weibo['age'] = ''
                                t += 1
                            except Exception as e:
                                break
                            if flag1 and flag2:
                                break

    def get_one_page(self, html):
        selecter = etree.HTML(html)
        k = 1
        while True:
            weibo = dict()
            try:
                div = selecter.xpath('//*[@id="pl_feedlist_index"]/div[2]/div[{}]'.format(k))
                if len(div) == 0:
                    break
                name = selecter.xpath('//*[@id="pl_feedlist_index"]/div[2]/div[{}]/div/div[1]/div[2]/div[1]/div[2]/a'.format(k))
                weibo['name'] = name[0].text.strip() if len(name) > 0 else ''

                content = selecter.xpath(
                    '//*[@id="pl_feedlist_index"]/div[2]/div[{}]/div/div[1]/div[2]/p[1]'.format(k))
                weibo['content'] = content[0].xpath('string(.)').strip() if len(content) > 0 else ''

                release_time = selecter.xpath(
                    '//*[@id="pl_feedlist_index"]/div[2]/div[{}]/div/div[1]/div[2]/p[@class="from"]/a[1]'.format(k))
                weibo['release_time'] = release_time[0].xpath('string(.)').strip() if len(release_time) > 0 else ''

                transpond = selecter.xpath(
                    '//*[@id="pl_feedlist_index"]/div[2]/div[{}]/div/div[2]/ul/li[2]/a'.format(k))
                transpond = transpond[0].text if len(transpond) > 0 else ''
                transpond = self.extract_digit(transpond)
                if transpond:
                    weibo['transpond_num'] = transpond
                else:
                    weibo['transpond_num'] = 0

                comment = selecter.xpath(
                    '//*[@id="pl_feedlist_index"]/div[2]/div[{}]/div/div[2]/ul/li[3]/a'.format(k))
                comment = comment[0].text if len(comment) > 0 else ''
                comment = self.extract_digit(comment)
                if comment:
                    weibo['comment_num'] = comment
                else:
                    weibo['comment_num'] = 0

                thumbsup = selecter.xpath(
                    '//*[@id="pl_feedlist_index"]/div[2]/div[{}]/div/div[2]/ul/li[4]/a/em'.format(k))
                thumbsup = thumbsup[0].text if len(thumbsup) > 0 else ''
                thumbsup = self.extract_digit(thumbsup)
                if thumbsup:
                    weibo['thumbsup_num'] = thumbsup
                else:
                    weibo['thumbsup_num'] = 0

                homepage_url = selecter.xpath(
                    '//*[@id="pl_feedlist_index"]/div[2]/div[{}]/div/div[1]/div[2]/div[1]/div[2]/a[1]/@href'.format(k))
                homepage_url = homepage_url[0] if len(homepage_url) > 0 else ''
                if homepage_url:
                    h = homepage_url[2:].split('/')
                    if h[1] == 'u':
                        weibo['uid'] = h[2].split('?')[0]
                    else:
                        weibo['uid'] = h[1].split('?')[0]
                    homepage_url = 'https:' + homepage_url
                    self.get_detail_info(homepage_url, weibo)
            except Exception as e:
                print(traceback.print_exc())
                break
            k += 1
            self.weibo.append(weibo)

    def save(self):
        columns_map = {
            'name': '微博名称',
            'location': '微博所在地',
            'gender': '性别',
            'content': '微博内容',
            'transpond_num': '转发量',
            'comment_num': '评论量',
            'thumbsup_num': '点赞量',
            'uid': '用户ID',
            'age': '年龄',
            'release_time': '发布时间'
        }
        df = pd.DataFrame(self.weibo)
        df.rename(columns=columns_map, inplace=True)

        columns = ['微博名称', '用户ID', '性别', '年龄', '微博所在地', '微博内容', '发布时间', '转发量', '评论量', '点赞量']
        df.to_excel('./data/{}年{}月{}日.xlsx'.format(self.year, self.month, self.day), columns=columns)

    def start(self):
        page_index = 1
        while True:
            url = 'https://s.weibo.com/weibo?q={}&typeall=1&suball=1&timescope=custom:{}-{}-{}-0:{}-{}-{}-23&Refer=g&page={}'.format(
                self.query, self.year, str(self.month).zfill(2), str(self.day).zfill(2), self.year, str(self.month).zfill(2), str(self.day).zfill(2), page_index)
            if page_index == 51:
                break
            try:
                res = requests.get(url, headers=self.headers, cookies=self.cookie)
            except Exception as e:
                print(e)
                page_index += 1
                continue
            self.set_encoding(res)
            html = res.text
            if '新浪通行证' in html:
                self.cookie = self.get_cookie()
                res = requests.get(url, headers=self.headers, cookies=self.cookie)
                self.set_encoding(res)
                html = res.text
                print('cookie updated!')
            print('正在抓取{}年{}月{}日 第{}页数据'.format(self.year, self.month, self.day, page_index))
            try:
                self.get_one_page(html)
            except NoResultException as e:
                print(e)
                break
            time.sleep(0.5)
            page_index += 1
        self.save()


def main():
    blacklist_file = 'blacklist.txt'  # 黑名单文件
    config = {
        'query': '共享单车',  # 查询关键词
        'start_month': 1,  # 开始月份
        'start_day': 1,  # 开始天数
        'username': 'xxxxxxxxxxxx',  # 账号
        'password': 'xxxxxxxxxxxx',  # 密码
    }
    years = ['2018', '2019']
    config = Config(**config)

    if not os.path.exists(blacklist_file):
        open(blacklist_file, 'w').close()  # 如果黑名单不存在就创建

    if not os.path.exists('./data'):
        os.makedirs('./data')
    for year in years:
        for month in range(config.start_month, 13):
            for day in range(config.start_day, 32):
                with open(blacklist_file) as f:
                    blacklist = [line.strip() for line in f.readlines()]
                if '{}-{}-{}'.format(year, month, day) in blacklist:
                    continue
                config.year = year
                config.month = month
                config.day = day
                ws = WeiboSpider(config)
                ws.start()
                with open(blacklist_file, 'a') as f:
                    f.write('{}-{}-{}\n'.format(year, month, day))

    print("数据抓取并保存完成")


if __name__ == '__main__':
    main()
