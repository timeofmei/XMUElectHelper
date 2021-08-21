import httpx
import os
import getpass
import base64
import time
import random
import execjs
import threading
from lxml.etree import HTML

class Student:
    def __init__(self):
        self.baseUrl = "http://xk.xmu.edu.cn"
        try:
            print("-" * 30 + "\n")
            print("正在进行网络测试")
            self.connectionOK = httpx.get(self.baseUrl).status_code == 200
            if self.connectionOK:
                print("网络正常")
            else:
                print("网不好/选课网站崩了, 没得办法")
            print(self.dashLine)
        except:
            self.connectionOK = False
            print("网不好/选课网站崩了, 没得办法")
        self.loggedIn = False
        self.cancelList = ['n', 'N', 'no', 'No', 'NO', 'nO', '否', '0']
        self.classList = []
        self.dashLine = "\n" + "-" * 30 + "\n"
        self.campus = 1
        self.authInfo = {
            "Authorization": "",
            "batchId": ""
        }
        self.classTypes = {
            "本专业计划课程": "TJKC",
            "本专业其他年级课程": "FANKC",
            "方案外课程": "FAWKC",
            "重修课程": "CXKC",
            "体育/大学英语课程": "TYKC",
            "校选课": "XGKC",
            "辅修课程": "FX"
        }


    def _encryptPassword(self, password):
        loginPage = HTML(httpx.get(self.baseUrl + "/xsxkxmu/profile/index.html").text)
        aesKey = loginPage.xpath("//body/script[7]/text()")[0].split("\"")[-4]
        return execjs.compile(r"""
        function enc(password, aesKey) {
            const CryptoJS = require("crypto-js");
            return CryptoJS.AES.encrypt(CryptoJS.enc.Utf8.parse(password), CryptoJS.enc.Utf8.parse(aesKey), {
                mode: CryptoJS.mode.ECB,
                padding: CryptoJS.pad.Pkcs7
            }).toString()
        }
        """).call("enc", password, aesKey)


    def _getCaptcha(self):
        print("正在获取验证码")
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
            xueHao = input("学号: ").strip()
            if len(xueHao) != 14:
                continue
            password = self._encryptPassword(getpass.getpass("密码: ")).strip()
            while True:
                captchaUUID, captchaResult = self._getCaptcha()
                loginData = {
                    "loginname": xueHao,
                    "password": password,
                    "captcha": captchaResult,
                    "uuid": captchaUUID
                }
                print("正在登录")
                login = httpx.post(self.baseUrl + "/xsxkxmu/auth/login", data=loginData).json()
                if login["code"] == 200:
                    print("登录成功")
                    print(self.dashLine)
                    self.loggedIn = True
                    stuData = login["data"]
                    self.campus = int(stuData["student"]["campus"])
                    batchList = [{"name": batch["name"], "code": batch["code"]} for batch in stuData["student"]["electiveBatchList"]]
                    for i, batch in enumerate(batchList):
                        print(f"{i+1}. {batch['name']}")
                    while True:
                        try:
                            batchNo = int(input("\n选课批次编号: "))
                            self.authInfo["Authorization"] = stuData["token"]
                            self.authInfo["batchId"] = batchList[batchNo - 1]["code"]
                            print(self.dashLine)
                            return self
                        except:
                            print(f"选课批次 {batchNo} 不存在")
                else:
                    print("\n" + login["msg"])
                    if login["msg"] == "用户不存在/密码错误":
                        break


    def getClassList(self):
        if not self.loggedIn:
            return self
        while True:
            while True:
                try:
                    classTypeNames = list(self.classTypes)
                    for i, classType in enumerate(classTypeNames):
                        print(f"{i+1}. {classType}")
                    classTypeNo = int(input("\n课程类型编号: "))
                    classType = self.classTypes[classTypeNames[classTypeNo - 1]]
                    break
                except Exception as e:
                    print(e)
                    print(f"课程类型 {classTypeNo} 不存在")
                    continue
            while True:
                try:
                    pageNo = int(input("页码: "))
                    if pageNo <= 0:
                        raise IndexError
                    break
                except:
                    continue
            jsonParams = {
                "teachingClassType": classType,
                "pageNumber": pageNo,
                "pageSize": 10,
                "orderBy": "",
                "campus": self.campus
            }
            resp = httpx.post(self.baseUrl + "/xsxkxmu/elective/clazz/list", headers=self.authInfo, json=jsonParams).json()
            if resp["code"] != 200:
                print(resp["msg"])
                if resp["code"] == 401:
                    print("可能是批次选择错误, 请重试")
                return self
            classData = resp["data"]["rows"]
            if classData == []:
                print("本页无课程")
            else:
                print("\n")
            classList = []
            for classInfo in classData:
                for tcInfo in classInfo["tcList"]:
                    classList.append({
                        "课程名": classInfo["KCM"],
                        "课程属性": classType,
                        "clazzId": tcInfo["JXBID"],
                        "secretVal": tcInfo["secretVal"],
                        "教师": tcInfo["SKJS"],
                        "上课时间地点": tcInfo["teachingPlace"],
                        "容量": tcInfo["classCapacity"],
                        "已报第一志愿": tcInfo["numberOfFirstVolunteer"],
                        "已选中人数": tcInfo["numberOfSelected"]
                    })
            self.classList.extend(classList)
            for i, cls in enumerate(self.classList):
                selectedNum = cls['已选中人数'] if cls['已选中人数'] != 0 else cls["已报第一志愿"]
                print(f"{i+1}. {cls['课程名']} {cls['教师']} {selectedNum}/{cls['容量']} {cls['上课时间地点']}")
            continueLoading = input("\n是否加载其他页面课程(y/n): ").strip()
            print(self.dashLine)
            if continueLoading in self.cancelList:
                break
        return self


    def _addClass(self, classId):
        cl = self.classList[classId - 1]
        return {
            "课程名": cl["课程名"],
            "教师": cl["教师"],
            "上课时间地点": cl["上课时间地点"],
            "headers": self.authInfo,
            "params": {
            "clazzType": cl["课程属性"],
            "clazzId": cl["clazzId"],
            "secretVal": cl["secretVal"],
            "chooseVolunteer": 1
        }}


    def _electWorker(self, headers, params, className):
        i = 0
        while True:
            time.sleep(random.uniform(0.7, 0.9))
            try:
                result = httpx.post(self.baseUrl + "/xsxkxmu/elective/clazz/add", headers=headers, params=params).json()
                i += 1
            except:
                continue
            print(f"{className} 第 {i} 次尝试 {result['msg']}")
            if result["code"] == 200 or result["msg"] == "该课程已在选课结果中" or result["msg"] == "所选课程与已选课程冲突":
                break


    def electClass(self):
        if not self.loggedIn or self.classList == []:
            return self
        while True:
            electList = []
            electThreads = []
            classIds = input("课程编号, 用' '分隔: ").split(" ")
            if not classIds:
                continue
            for classId in classIds:
                try:
                    id = int(classId)
                    if id > len(self.classList) or id <= 0:
                        print(f"课程 {id} 不存在")
                        raise IndexError
                    electList.append(self._addClass(id))
                except:
                    continue
            print(self.dashLine)
            if electList == []:
                continue
            print("选课列表: ")
            for i, election in enumerate(electList):
                print(f"{i+1}. {election['课程名']} {election['教师']} {election['上课时间地点']}")
            if input("\n待选课程是否正确(y/n):") in self.cancelList:
                continue
            print(self.dashLine)
            print("开始选课")
            print(self.dashLine)
            for election in electList:
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
