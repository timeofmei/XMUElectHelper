import httpx
import os
import base64
import json
import execjs
from lxml.etree import HTML

class Student:
    def __init__(self, xueHao, password):
        self.baseUrl = "http://xk.xmu.edu.cn"
        self.add = {}
        self.campusMap = {
            "思明": 1,
            "翔安": 6,
            "漳州": 9
        }
        self.classTypeMap = {
            "推荐课程": "TJKC",
            "方案内课程": "FANKC",
            "方案外课程": "FAWKC",
            "重修课程": "CXKC",
            "体育课": "TYKC",
            "校选课": "XGKC",
            "辅修课程": "FXKC",
            "全校课程": "ALLKC",
        }
        self.xueHao = xueHao
        self.password = self.encryptPassword(password)
        with open("ZXYX.json") as ZXYX:
            self.depdic = json.loads(ZXYX.read())


    def encryptPassword(self, password):
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


    def crackCaptcha(self):
        captchaData = httpx.post(self.baseUrl + "/xsxkxmu/auth/captcha").json()["data"]
        captchaUUID = captchaData["uuid"]
        captchaContent = captchaData["captcha"].split(",")[1]
        captchaBin = base64.b64decode(captchaContent)
        f = open("captcha.jpg", "wb")
        f.write(captchaBin)
        f.close()
        captchaResult = input("验证码: ")
        os.remove("captcha.jpg")
        return (captchaUUID, captchaResult)


    def login(self):
        while True:
            captchaUUID, captchaResult = self.crackCaptcha()
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


    def crawl(self, classType, pageNumber, campus, depName):
        campus = self.campusMap[campus]
        if classType == "已选课程":
            classUrl = "/xsxkxmu/volunteer/select"
        else:
            classType = self.classTypeMap[classType]
            classUrl = "/xsxkxmu/elective/clazz/list"
        for depOfficialName, depNo in self.depdic.items():
            if depName in depOfficialName:
                break
        jsonParams = {
            "teachingClassType": classType,
            "pageNumber": pageNumber,
            "pageSize": 10,
            "orderBy": "",
            "campus": campus,
            "ZXYX": depNo
        }
        resp = httpx.post(self.baseUrl + classUrl, headers={"Authorization": self.token}, json=jsonParams).json()
        if resp["code"] != 200:
            print(resp["msg"])
            return self
        classData = resp["data"]
        classList = []
        for classInfo in classData["rows"]:
            tcInfos = []
            for tcInfo in classInfo["tcList"]:
                tcInfos.append({
                    "clazzId": tcInfo["JXBID"],
                    "secretVal": tcInfo["secretVal"],
                    "教师": tcInfo["SKJS"],
                    "容量": tcInfo["classCapacity"],
                    "已报第一志愿": tcInfo["numberOfFirstVolunteer"],
                    "已选中人数": tcInfo["numberOfSelected"],
                    "上课地点时间": tcInfo["teachingPlace"],
                    "上课校区": tcInfo["XQ"]
                })
            classList.append({
                "课程名": classInfo["KCM"],
                "类别": classInfo["KCLB"],
                "学院": classInfo["KKDW"],
                "性质": classInfo["KCXZ"],
                "学时": classInfo["hours"],
                "授课信息": tcInfos
            })
        self.classList = classList
        return self
    
    def findClass(self, className):
        for cl in self.classList:
            if cl["课程名"] == className:
                self.add["headers"] = {
                    "Authorization": self.token,
                    "batchId": self.batchId,
                }
                self.add["params"] = {
                    "clazzType": "FAWKC",
                    "clazzId": cl["授课信息"][0]["clazzId"],
                    "secretVal": cl["授课信息"][0]["secretVal"]
                }
                return True
        return False
    def crackClass(self):
        className = input("课程名: ")
        while True:
            if self.findClass(className):
                break
            className = input("重新输入课程名: ")
            
        while True:
            resp = httpx.post(self.baseUrl + "/xsxkxmu/elective/clazz/add", headers=self.add["headers"], params=self.add["params"]).json()
            print(resp)
            if resp["code"] == 200:
                return True
            elif resp["code"] == 401:
                self.login()


if __name__ == "__main__":
    with open("loginInfo.json") as f:
        loginInfo = json.loads(f.read())
    me = Student(loginInfo["xueHao"], loginInfo["password"])
    me.login()
    campus = input("校区(思明, 翔安, 漳州): ")
    depName = input("学院: ")
    me.crawl("方案外课程", 1, campus, depName)
    for cls in me.classList:
        print("- " +cls["课程名"])
    me.crackClass()
