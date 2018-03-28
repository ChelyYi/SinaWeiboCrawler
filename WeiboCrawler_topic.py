#-*- coding:utf-8 -*-

import base64
import json
import re
import urllib.request,urllib.error,urllib.parse
import rsa
import binascii
import time
from bs4 import BeautifulSoup

import http.cookiejar

class WeiboCrawler:

    def __init__(self,username,password):
        """
        :param username: login username
        :param password: login password
        """
        self.__password = password
        self.__username = username

    def __get_encrypted_name(self):
        """
        用户名加密，使用base64算法加密
        :return:加密后的用户名
        """
        username_urllike = urllib.request.quote(self.__username)
        username_encrypted = base64.b64encode(bytes(username_urllike,encoding='utf-8'))
        #print(username_encrypted)
        return username_encrypted.decode('utf-8')

    def __get_prelogin_args(self):
        """
        模拟预登陆过程（输入用户名之后触发），获取服务器返回的nonce，servertime，pub_key等信息
        :return 返回的json串
        """
        json_pattern = re.compile('\((.*)\)')
        url = 'http://login.sina.com.cn/sso/prelogin.php?entry=weibo&callback=sinaSSOController.preloginCallBack&su=&' + self.__get_encrypted_name() + '&rsakt=mod&checkpin=1&client=ssologin.js(v1.4.18)'
        try:
            req = urllib.request.Request(url)
            response = urllib.request.urlopen(req)
            raw_data = response.read().decode('utf-8')
            json_data = json_pattern.search(raw_data).group(1)
            data = json.loads(json_data)
            #print("Prelog data:", data)
            return data
        except urllib.error as e:
            print("%d"%e.code)
            return None

    def __get_encrypted_pw(self,data):
        """
        采用RSA加密方式，公钥在prelog环节获得 具体加密方式在sso_login.js代码中
        :param data:prelog环节得到的数据，包括加密要用到的servertime,nounce,pubkey信息
        :return:加密后的密码
        """
        #data = self.get_prelogin_args()
        rsa_e = 65537 #0x10001,js代码中提供
        pw_string = str(data['servertime']) + '\t' + str(data['nonce']) + '\n'+str(self.__password)
        key = rsa.PublicKey(int(data['pubkey'],16),rsa_e)
        pw_encrypted = rsa.encrypt(pw_string.encode('utf-8'),key)
        self.__password = '' # clear password for security
        passwd = binascii.b2a_hex(pw_encrypted)
        #print("Password encoded ",passwd)
        return passwd

    def __enable_cookies(self):
        # build a cookie container
        cookie_container = http.cookiejar.CookieJar()
        #将一个cookie容器和一个HTTP的Cookie处理器绑定
        cookie_support = urllib.request.HTTPCookieProcessor(cookie_container)
        #创建一个opener，设置一个handler用于处理http的url打开
        opener = urllib.request.build_opener(cookie_support,urllib.request.HTTPHandler)
        #安装opener，此后调用urlopen()时会使用安装过的opener对象
        urllib.request.install_opener(opener)

        return opener

    def __build_post_data(self,raw):
        post_data = {
            "entry": "weibo",
            "gateway": "1",
            "from": "",
            "savestate": "7",
            "useticket": "1",
            "pagerefer": "http://passport.weibo.com/visitor/visitor?entry=miniblog&a=enter&url=http%3A%2F%2Fweibo.com%2F&domain=.weibo.com&ua=php-sso_sdk_client-0.6.14",
            "vsnf": "1",
            "su": self.__get_encrypted_name(),
            "service": "miniblog",
            "servertime": raw['servertime'],
            "nonce": raw['nonce'],
            "pwencode": "rsa2",
            "rsakv": raw['rsakv'],
            "sp": self.__get_encrypted_pw(raw),
            "sr": "1280*800",
            "encoding": "UTF-8",
            "prelt": "77",
            "url": "http://weibo.com/ajaxlogin.php?framelogin=1&callback=parent.sinaSSOController.feedBackUrlCallBack",
            "returntype": "META"
        }
        data = urllib.parse.urlencode(post_data).encode('utf-8')
        return data


    def login(self):
        print("Logining...\n")
        url = 'http://login.sina.com.cn/sso/login.php?client=ssologin.js(v1.4.18)'
        opener = self.__enable_cookies()
        data = self.__get_prelogin_args()
        post_data = self.__build_post_data(data)
        headers = {
            "User-Agent":"Mozilla/5.0 (Windows NT 6.1; rv:24.0) Gecko/20100101 Firefox/24.0",
            "Connection": "keep - alive",
            "Upgrade - Insecure - Requests": "1"
        }
        try:
            req = urllib.request.Request(url,post_data,headers)
            response = urllib.request.urlopen(req)

            html = response.read().decode('GBK')
            #print(html)
        except urllib.error as e:
            print(e.code)

        p = re.compile('location\.replace\(\'(.*?)\'\)')
        p2 = re.compile(r'"userdomain":"(.*?)"')

        try:
            login_url = p.search(html).group(1)
            #print(login_url)
            req = urllib.request.Request(login_url)
            response = urllib.request.urlopen(req)
            page = response.read().decode('utf-8')
            #print(page)
            login_url = 'http://weibo.com/' + p2.search(page).group(1)
            req2 = urllib.request.Request(login_url)
            response = urllib.request.urlopen(req2)
            final = response.read().decode('utf-8')
            #print(final)

            print("Login success!\n")
            return opener
        except:
            print('Login error!')
            return None

    def leap_year(self,year):
        if (year % 4) == 0:
            if (year % 100) == 0:
                if (year % 400) == 0:
                    return True  # 整百年能被400整除的是闰年
                else:
                    return False
            else:
                return True  # 非整百年能被4整除的为闰年
        else:
            return False

    def __urlencode(self,topic):
        """
        搜索内容使用urlencode编码，Sina微博还会在%后面加上数字25
        :param topic: 搜索内容
        :return: string after encoding
        """
        urlcode = urllib.parse.quote(topic)
        urlcode = urlcode.replace('%','%25')
        return urlcode


    def get_page(self,year,month,topic):
        opener = self.login()
        monthes = [31,28,31,30,31,30,31,31,30,31,30,31] # days of every month
        if self.leap_year(year) is True:# leap year
            monthes[1] = 29
        days = monthes[month-1] # get days of specific month
        urlcode = self.__urlencode(topic) # search content

        for d in range(1,days+1,1): # every day
            for h in range(0,24,1): # every hour
                date = str(year)+"-"+ str(month)+"-"+str(d)+"-"+str(h)
                page_url = 'https://s.weibo.com/weibo/'+urlcode+'&scope=ori&suball=1&timescope=custom:'+ date+ ':'+ date
                print(page_url)
                req = urllib.request.Request(page_url)
                response = opener.open(req)
                web = response.read().decode('utf-8')
                # the first page, get total pages number
                page_num = self.__extract_text(web,topic,get_page=True)
                time.sleep(17)

                if page_num == -1: # only one page or no result
                    continue
                else: # more than one page
                    for k in range(2, page_num + 2, 1):  # every page, except for the first one
                        page_url = 'https://s.weibo.com/weibo/'+urlcode+'&scope=ori&suball=1&timescope=custom:' + date + ':' + date + "&page=" + str(k)
                        print(page_url)
                        req = urllib.request.Request(page_url)
                        response = opener.open(req)
                        web = response.read().decode('utf-8')
                        self.__extract_text(web,topic)

                        time.sleep(17)


    def __extract_text(self,web,topic,get_page=False):
        """
        Used for extract text information in html page
        :param web: html web page
        :param get_page: whether get pages' number of all search result,usually set True when the first page
        :return: text(str)
        """
        write_file = open('./data/weibo_trump','a',encoding='utf-8')
        soup = BeautifulSoup(web, "html.parser")
        result = soup.find_all('script')
        #print(result[20])  # Count script no.20
        content = result[20].text  # get text
        #print(content)

        p = re.compile('\{(.|\n)+\}')
        match_string = p.search(content).group()
        #print(match_string) # a json string, contains html
        json_string = json.loads(match_string)
        if (json_string["pid"] != "pl_weibo_direct"):
            raise Exception("Extract wrong script")

        html = json_string["html"]
        html_soup = BeautifulSoup(html, "html.parser")
        # print(html_soup.prettify())

        noresult = html_soup.find("div",attrs={"class":"search_noresult"})
        if noresult != None: # no search result
            print("No search result!")
            return -1

        weibo = html_soup.find_all("div", class_="feed_content wbcon") # weibo content part
        #print(weibo)
        for item in weibo:
            user_name = item.a.text.strip()
            p_tag = item.find("p", attrs={"class": "comment_txt", "node-type": "feed_list_content"})  # weibo content

            # unfold all weibo content
            a_unfold = p_tag.find("a", attrs={"action-type": "fl_unfold"})
            if a_unfold != None:
                # print(a_unfold['action-data'])
                # something wrong, encoding, so match the information
                p1 = re.compile('mid=(\w)+&search=(\w|%)+&absstr=(\w|%)+')
                p2 = re.compile('uid=(\d)+')
                p3 = re.compile('mid=(\d)+')
                part1 = p1.match(a_unfold['action-data']).group()
                part2 = p2.search(a_unfold['action-data']).group()
                part3 = p3.search(a_unfold['action-data']).group()
                url = "https://s.weibo.com/ajax/direct/morethan140?" + part1 + part2 + "&" + part3
                #print(url)

                req = urllib.request.Request(url)
                response = urllib.request.urlopen(req)
                result_json = json.loads(response.read().decode('utf-8'))
                # print(result_json['data'])
                all_text = result_json['data']['html']

                p_tag = BeautifulSoup(all_text, 'html.parser')
                # print(p_tag.text)

            [a.extract() for a in p_tag.find_all("a", class_="W_btn_c6")]  # remove web links
            a_list = p_tag.find_all("a")  # remove @ username
            for a in a_list:
                if a.has_attr('usercard'):
                    a.extract()

            weibo_content = p_tag.text.strip()
            weibo_content = weibo_content.replace('\n',' ')
            weibo_content = weibo_content.replace('\t', ' ')
            if weibo_content.startswith('//'):
                continue

            if topic in weibo_content:
                print(user_name, "\t", weibo_content)
                write_file.write(user_name+"\t"+weibo_content+"\n")

        # get pages number
        if get_page is True:
            pages = html_soup.find("div",attrs={"class": "layer_menu_list W_scroll", "node-type": "feed_list_page_morelist",
                                          "action-type": "feed_list_page_morelist"})
            if pages is None: # only one page
                return -1
            else:
                pages_list = pages.find_all(self.is_page)
                #print(pages_list)
                return len(pages_list)

    def is_page(self,tag):
        return tag.has_attr('suda-data')


if __name__ == '__main__':

    crawler = WeiboCrawler(account,password)
    #crawler.test()
    crawler.get_page(year=2018,month=2,topic="特朗普")
