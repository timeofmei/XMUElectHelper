import httpx
import os
import getpass
import base64
import json
import time
import random
import execjs
import threading
from lxml.etree import HTML


class Student:
    def __init__(self):
        self.baseUrl = "http://xk.xmu.edu.cn"
        try:
            self.connectionOK = httpx.get(self.baseUrl).status_code == 200
        except:
            print("网不好/选课网站崩了, 没得办法")
            self.connectionOK = False
        with open("mappings.json") as mappings:
            maps = json.loads(mappings.read())
            self.campusMap = maps["campus"]
            self.classTypeMap = maps["classType"]
            self.depMap = maps["ZXYX"]
            self.classList = []


    def _encryptPassword(self, password):
        loginPage = HTML(httpx.get(self.baseUrl + "/xsxkxmu/profile/index.html").text)
        self.batchId = loginPage.xpath("//body/script[7]/text()")[0].split(":")[1].split("\"")[1]
        aesKey = loginPage.xpath("//body/script[7]/text()")[0].split("\"")[-4]
        return execjs.compile(r"""
        function enc(password, aesKey) {
            var CryptoJS = require("crypto-js");
            return CryptoJS.AES.encrypt(CryptoJS.enc.Utf8.parse(password), CryptoJS.enc.Utf8.parse(aesKey), {
                mode: CryptoJS.mode.ECB,
                padding: CryptoJS.pad.Pkcs7
            }).toString()
        }
        """).call("enc", password, aesKey)


    def _electCaptcha(self):
        captchaData = httpx.post(self.baseUrl + "/xsxkxmu/auth/captcha").json()["data"]
        captchaUUID = captchaData["uuid"]
        captchaContent = captchaData["captcha"].split(",")[1]
        captchaBin = base64.b64decode(captchaContent)
        with open("captcha.jpg", "wb") as f:
            f.write(captchaBin)
        captchaResult = input("验证码: ")
        os.remove("captcha.jpg")
        return (captchaUUID, captchaResult)


    def login(self):
        while True:
            self.xueHao = input("学号: ").strip()
            if len(self.xueHao) != 14:
                continue
            self.password = self._encryptPassword(getpass.getpass("密码: ")).strip()
            while True:
                captchaUUID, captchaResult = self._electCaptcha()
                loginData = {
                    "loginname": self.xueHao,
                    "password": self.password,
                    "captcha": captchaResult,
                    "uuid": captchaUUID
                }
                login = httpx.post(self.baseUrl + "/xsxkxmu/auth/login", data=loginData).json()
                if login["code"] == 200:
                    print("登录成功")
                    self.stuData = login["data"]
                    self.stuInfo = self.stuData["student"]
                    self.token = self.stuData["token"]
                    return self
                else:
                    print(login["msg"])
                    if login["msg"] == "用户不存在/密码错误":
                        break


    def getClassList(self):
        while True:
            try:
                campus = self.campusMap[input("校区(思明, 翔安, 漳州): ")]
                break
            except KeyError:
                pass
        while True:
            try:
                depName = input("学院: ")
                depFound = False
                for depOfficialName, depNo in self.depMap.items():
                    if depName in depOfficialName:
                        depFound = True
                        break
                if not depFound:
                    raise KeyError
                break
            except KeyError:
                pass
        while True:
            while True:
                try:
                    classType = self.classTypeMap[input("课程类型(推荐课程, 方案内课程, 方案外课程, 重修课程, 体育课, 校选课, 辅修课程): ")]
                    break
                except KeyError:
                    pass
            while True:
                try:
                    pageNumber = int(input("页码: "))
                    break
                except:
                    pass
            jsonParams = {
                "teachingClassType": classType,
                "pageNumber": pageNumber,
                "pageSize": 10,
                "orderBy": "",
                "campus": campus,
                "ZXYX": depNo
            }
            resp = httpx.post(self.baseUrl + "/xsxkxmu/elective/clazz/list", headers={"Authorization": self.token}, json=jsonParams).json()
            if resp["code"] != 200:
                print(resp["msg"])
                return self
            classData = resp["data"]
            classList = []
            for classInfo in classData["rows"]:
                tcInfos = []
                for tcInfo in classInfo["tcList"]:
                    keys = list(tcInfo.keys())
                    tcInfos.append({
                        "clazzId": tcInfo["JXBID"],
                        "secretVal": tcInfo["secretVal"],
                        "教师": tcInfo["SKJS"],
                        "容量": tcInfo["classCapacity"],
                        "已报第一志愿": tcInfo["numberOfFirstVolunteer"],
                        "已选中人数": tcInfo["numberOfSelected"],
                        "上课地点时间": tcInfo["teachingPlace"] if "teachingPlace" in keys else "",
                        "上课校区": tcInfo["XQ"]
                    })
                classList.append({
                    "课程名": classInfo["KCM"],
                    "类别": classInfo["KCLB"],
                    "学院": classInfo["KKDW"],
                    "性质": classInfo["KCXZ"],
                    "学时": classInfo["hours"],
                    "课程属性": classType,
                    "授课信息": tcInfos
                })
            self.classList.extend(classList)
            for cls in self.classList:
                print("- " + cls["课程名"])
                for tcInfo in cls["授课信息"]:
                    print("   ", tcInfo["教师"], tcInfo["已选中人数"] + "/" + tcInfo["容量"])
            if input("\n是否选择其他页面课程?(y/n)").strip() in ['n', 'N', 'no', 'No', 'NO', 'nO', '否', '0']:
                break
        return self


    def _addClass(self, className):
        for cl in self.classList:
            if cl["课程名"] == className:
                self.electList.append({
                    "课程名": className,
                    "headers":  {
                    "Authorization": self.token,
                    "batchId": self.batchId,
                },
                "params": {
                    "clazzType": cl["课程属性"],
                    "clazzId": cl["授课信息"][0]["clazzId"],
                    "secretVal": cl["授课信息"][0]["secretVal"]
                }})
                return True
        return False


    def _electWorker(self, headers, params, className):
        while True:
            time.sleep(random.uniform(0.6, 0.8))
            try:
                result = httpx.post(self.baseUrl + "/xsxkxmu/elective/clazz/add", headers=headers, params=params).json()
            except:
                continue
            print(className + " " + result["msg"])
            if result["code"] == 200:
                return True


    def electClass(self):
        while True:
            self.electList = []
            electThreads = []
            classNamesRaw = input("课程名, 用' '分隔: ")
            classNames = classNamesRaw.split(" ")
            if not classNames:
                continue
            for className in classNames:
                self._addClass(className)
            for election in self.electList:
                electThreads.append(threading.Thread(target=self._electWorker, kwargs={
                    "headers": election["headers"], 
                    "params": election["params"], 
                    "className": election["课程名"]
                }))
            for thread in electThreads:
                thread.start()
            for thread in electThreads:
                thread.join()
            break


if __name__ == "__main__":
    me = Student()
    if me.connectionOK:
        me.login().getClassList().electClass()
