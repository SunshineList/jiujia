import base64
import datetime
import json
import random
import sys
from urllib.parse import urljoin

import threading
import re
import time
import hashlib
import requests
import urllib3
from Crypto.Cipher import AES
from Crypto.SelfTest.st_common import a2b_hex, b2a_hex
from Crypto.Util.Padding import pad, unpad
from PyQt5 import QtWidgets, QtCore, QtGui

urllib3.disable_warnings()

class Zmyy(object):
    def __init__(self, cookie=None, hospital_id=None, tags="九价"):
        self.flag = True
        self.sign = None
        self.host = "https://cloud.cn2030.com"
        self.request_instance = requests.Session()
        self.hospital_id = hospital_id
        self.mxid = {}
        self.date_mxid = []
        self.p_id = None
        self.wait_speed = 1000
        self.buy_speed = 1000
        self.tags = tags
        self.request = requests.Session()
        self.cookie = cookie
        self.r_cookie = None
        self.person_info = {
            "birthday": "",
            "tel": "",
            "sex": "",
            "cname": "",
            "idcard": "",
        }

    def _url(self, host, url) -> str:
        return urljoin(host, url)

    def _request(self, url, data, *, method="post", **kwargs):
        """
        通用request类 这里处理请求
        """

        data_map = {"method": method, "url": self._url(kwargs.get("host", self.host), url), "timeout": 3, 'headers': self._header(), 'verify': False}

        need_request = kwargs.pop("need_request", None)

        if method == "get":
            data_map.update({"params": data})
        else:
            data_map.update({"data": data})

        try:
            response = self.request.request(**data_map, **kwargs)
            if need_request:
                return response.json(), response
            return response.json()
        except (requests.ConnectionError, requests.Timeout) as e:
            print("请求超时, 请重新按确定按钮")
            sys.exit(0)

        except ValueError:
            if need_request:
                return response.text, response
            return response.text

        except Exception as e:
            print(f"未知错误  {e}")
            sys.exit(0)

    def _get_zftsl(self):
        md5 = hashlib.md5()
        str_time = str(round(time.time() * 100))
        str1 = "zfsw_" + str_time
        md5.update(str1.encode("utf-8"))
        value = md5.hexdigest()
        return value

    def _header(self) -> json:
        headers = {
            'Host': 'cloud.cn2030.com',
            'Connection': 'keep-alive',
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.20(0x1800142f) NetType/WIFI Language/zh_CN',
            'content-type': 'application/json',
            'zftsl': self._get_zftsl(),
            'Referer': 'https://servicewechat.com/wx2c7f0f3c30d99445/92/page-frame.html',
            'Accept-Encoding': 'gzip,deflate, br'
        }
        return headers

    def get_decrypt(self, k, value, iv=b'1234567890000000'):
        try:
            cryptor = AES.new(k.encode('utf-8'), AES.MODE_CBC, iv)
            value_hex = a2b_hex(value)
            unpadtext = unpad(cryptor.decrypt(value_hex), 16, 'pkcs7')
            return json.loads(unpadtext)
        except Exception as e:
            print(f"解密错误：{e}")
            return False

    def get_encrypt(self, k, value, iv=b'1234567890000000'):
        try:
            value = value.encode('UTF-8')
            cryptor = AES.new(k.encode('utf-8'), AES.MODE_CBC, iv)
            text = pad(value, 16, 'pkcs7')
            ciphertext_hex = b2a_hex(cryptor.encrypt(text))
            return ciphertext_hex.decode().strip()
        except Exception as e:
            print(f"加密错误 {e}")
            return None

    def get_sign(self, cookie):  # 获取用户签名（用于解密）
        global Sign
        try:
            data = cookie.split('.')[1]
            missing_padding = 4 - len(data) % 4
            if missing_padding:
                data += '=' * missing_padding
            b = json.loads(base64.b64decode(data.encode("utf-8")).decode("utf-8"))
            b = b['val'].replace(' ', '').replace('\r\n', '')
            b = base64.b64decode(b)
            self.sign = re.findall(r'(?<=\\x00\\x00\\x10).{16}', str(b))[0]
            return True
        except Exception as e:
            print(f"获取签名错误：{e}")
            return False

    def get_mxid(self, scdate):
        """
        获取scdate日期当天的产品列表
        :param p_id:
        :type p_id:
        :param id:
        :type id:
        :param scdate:
        :type scdate:
        :return:
        :rtype:
        """
        list1 = []
        data = {
            'act': 'GetCustSubscribeDateDetail',
            'pid': self.p_id,
            'id': self.hospital_id,
            'scdate': scdate
        }
        response = self._request(url="/sc/wx/HandlerSubscribe.ashx", method="get", data=data)
        result = self.get_decrypt(self.sign, response)

        if not result:  # 这里可能解密失败(尝试过了 应该是机制问题)
            return False

        if (result["status"] == 200):
            if ('mxid' in str(result)):
                for i in result["list"]:
                    if (i['qty'] > 0):
                        list1.insert(0, i['mxid'])
                self.mxid[scdate] = list1
                return True
            else:
                print(f"{scdate} 没有mxid: {result} 即将处理下一个日期")
                return False
        else:
            print(f"状态码不为200: {result}")
            return False

    def get_date(self):
        current_date = datetime.datetime.now().strftime('%Y%m')
        payload = {
            'act': 'GetCustSubscribeDateAll',
            'pid': self.p_id,
            'id': self.hospital_id,
            'month': current_date
        }
        response = self._request(url="/sc/wx/HandlerSubscribe.ashx", method="get", data=payload)
        try:
            if (response["status"] == 200):
                if ('enable' in str(response)):
                    for date in response["list"]:
                        if (date["enable"] == True):
                            self.date_mxid.insert(0, date["date"])
                    return True
                else:
                    return False
            return False
        except TypeError as e:
            return False

    def yan_zheng_code(self, mxid):
        """
        请求查询是否获取验证码
        :param mxid:
        :type mxid:
        :return:
        :rtype:
        """
        payload = {
            'act': 'GetCaptcha',
            'mxid': mxid
        }
        response, request_instance = self._request(url="/sc/wx/HandlerSubscribe.ashx", method="get", data=payload, need_request=True)
        if request_instance.status_code == 200:
            self.r_cookie = request_instance
            self.set_Cookie(request_instance)
            if (response['status'] == 200):
                return True
        else:
            if request_instance.status_code == 404:
                print(f"验证码页面发生了 404 程序继续")
            else:
                print(f'状态: 有验证码：{response}')
            return False

    def send_order_post(self, mxid, scdate):
        """
        提交订单信息
        :param mxid:
        :type mxid:
        :param scdate:
        :type scdate:
        :return:
        :rtype:
        """
        postContext = '{"birthday":"%s","tel":"%s","sex":%s,"cname":"%s","doctype":1,"idcard":"%s","mxid":"%s","date":"%s","pid":"%s","Ftime":1,"guid":""}' % (
            self.person_info.get("birthday"), self.person_info.get("tel"), self.person_info.get("sex"),
            self.person_info.get("cname"), self.person_info.get("idcard"), mxid, scdate, self.p_id)

        postContext = self.get_encrypt(self.sign, postContext)
        response, request_instance = self._request(url="/sc/api/User/OrderPost", data=postContext, method="post", need_request=True)

        if ("eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9" not in request_instance.headers.get('set-cookie')):
            self.set_Cookie(self.r_cookie)

        if (response['status'] == 200):
            print(f"状态: {response['msg']}")
            return True
        else:
            print(f"状态: {response.get('msg')}")
            return False

    def get_order_status(self):
        """
        获取订单信息状态
        :return:
        :rtype:
        """
        payload = {
            'act': 'GetOrderStatus'
        }
        response = self._request(url="/sc/wx/HandlerSubscribe.ashx", data=payload, method="get")
        if (response['status'] == 200):
            print(f"结果: {response}")
            self.flag = False
            print('抢购成功！退出程序。')
            sys.exit(0)
        else:
            print(f"结果: {response['msg']}")
            return False

    def get_product_list(self):
        """
        获取门诊可预约的列表
        :param mz_id:
        :type mz_id:
        :return:
        :rtype:
        """
        pid_list = []  # 不排除有多个情况 这里

        payload = {
            "act": "CustomerProduct",
            "id": self.hospital_id
        }

        response = self._request(url="sc/wx/HandlerSubscribe.ashx", method="get", data=payload)
        product_list = response.get("list")

        if not product_list:
            print("暂无可预约内容")
            return

        for product in product_list:
            if product["enable"] == True:
                for tag in self.tags.split(","):
                    if tag in product["descript"] or tag in product["tags"] or tag in product["text"]:
                        print(f"{product}")
                        pid_list.append(product.get("id"))  # 如果有一个符合就加入 结束循环
                        break
        return pid_list

    def while_get_pid(self):
        """
        循环获取pid 如果获取不到死循环
        :return:
        :rtype:
        """
        counter = 0
        product_id = []
        while self.flag:
            try:
                product_id = self.get_product_list()
            except Exception as e:
                continue
            if product_id:
                break
            counter += 1
            time.sleep(1)
            print(f"未获取到疫苗 正在尝试获取第{counter}次")

        if len(product_id) == 1:
            return product_id

        if len(product_id) > 1:
            return random.choice(product_id)  # 随机返回一个出去

        return None

    def get_user_info(self):
        """
        获取用户基本信息
        :return:
        :rtype:
        """
        payload = {
            'act': 'User'
        }
        response = self._request(url="/sc/wx/HandlerSubscribe.ashx", method="get", data=payload)

        if not response:
            return False

        if (response['status'] == 200):
            self.person_info["birthday"] = response['user']['birthday']
            self.person_info["tel"] = response['user']['tel']
            self.person_info["sex"]= response['user']['sex']
            self.person_info["cname"]= response['user']['cname']
            self.person_info["idcard"]= response['user']['idcard']
            print(f"登录成功，用户：{self.person_info.get('cname')}")
            return True
        else:
            print(f'Cookie出错：{response}')
            sys.exit(0)


    def set_Cookie(self, request):  # 设置cookie
        try:
            del self.request.cookies['ASP.NET_SessionId']
            cookies = request.cookies
            self.request.cookies.update(cookies)
            cookie_dict = requests.utils.dict_from_cookiejar(request.cookies)
            new_cookie = cookie_dict['ASP.NET_SessionId']
            self.cookie = new_cookie
            return True
        except Exception as e:
            print(f"cookie出错：{e}")
            return False


    def seckill(self):
        for i in self.date_mxid:  # 循环日期列表获取接种列表
            max_retry = 0
            while max_retry <= 1  and self.flag:
                try:
                    cishu = 1
                    if (self.get_mxid(i)):
                        print(f"抢苗接种时间：{i}")
                        for mxid_now in self.mxid[i]:
                            print(f'开始第{cishu}次抢购 ({mxid_now}) ')
                            if (self.yan_zheng_code(mxid_now)):
                                time.sleep(int(self.buy_speed) / 1000)
                                if (self.send_order_post(mxid_now, i)):
                                    time.sleep(int(self.buy_speed) / 1000)
                                    if self.get_order_status():
                                        break
                                    time.sleep(int(self.buy_speed) / 1000)
                                    break
                            cishu += 1
                        break
                    else:
                        time.sleep(1)
                except Exception as e:
                    print(str(e))
                    time.sleep(1)
                max_retry += 1

    def main(self):
        """
        主函数
        :return:
        :rtype:
        """

        if not self.cookie or not self.hospital_id:
            print("请先完善填充 cookie 和 医院id")
            return
        rcr = requests.cookies.RequestsCookieJar()
        rcr.set('ASP.NET_SessionId', self.cookie)
        self.request.cookies.update(rcr)

        self.get_user_info()  # 获取用户信息
        self.get_sign(self.cookie)  # 生成解密秘钥

        self.p_id = self.while_get_pid()

        if not self.p_id:
            print(f"未获取到 标签为{self.tags}的疫苗")
        else:
            for i in range(100):
                self.date_mxid = []
                self.mxid = {}
                while not (self.get_date()) and self.flag:
                    try:
                        print(f'列表刷新：{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")}')
                        time.sleep(int(self.wait_speed) / 1000)
                    except Exception as e:
                        print(f'ERROR:{e}')
                if not self.flag:
                    break
                self.date_mxid.sort()
                print(f"当前有号源的日期: {self.date_mxid} (为[]已预约满)")
                print("开始抢苗")
                self.seckill()  # 程序运行窗口
                print("继续努力中...")

if __name__ == "__main__":
    # 先填cookie和医院id
    zmyy = Zmyy()
    zmyy.main()