import os
import re
from bs4 import BeautifulSoup
import requests
from urllib.parse import urlencode
from requests.exceptions import RequestException
from hashlib import md5
import UserAgent
import json
from configu import *
import pymongo
import time
from multiprocessing import Pool

client = pymongo.MongoClient(MONGODB_URL)
db = client.MONGODB_DB
collection = db.MONGODB_COLLECTION


# 列表页
def get_page(offset, keywords):
    params = {
        'offset': offset,
        'format': 'json',
        'keyword': keywords,
        'autoload': 'true',
        'count': '20',
        'cur_tab': '3',
        'from': 'gallery'
    }
    url = 'https://www.toutiao.com/search_content/?' + urlencode(params)
    try:
        response = requests.get(url, headers=UserAgent.get_user_agent())
        if response.status_code == 200:
            return response.text
        return None
    except RequestException:
        return None


def parse_page_index(html):
    # 转成json
    data = json.loads(html)
    if data and 'data' in data.keys():
        for item in data.get('data'):
            if 'article_url' in item.keys():
                yield {
                    'title': item.get('title'),
                    'image': item.get('article_url')
                }


# 详情页
def get_page_detail(url):
    try:
        response = requests.get(url, headers=UserAgent.get_user_agent())
        if response.status_code == 200:
            return response.text
        return None
    except RequestException:
        return None


def parse_page_detail(html, url):
    soup = BeautifulSoup(html, 'lxml')
    # CSS选择器获取信息
    title = '暂无标题'
    if soup.select('title'):
        title = soup.select('title')[0].get_text()
    # 正则获取信息
    images_pattern = re.compile('BASE_DATA.galleryInfo = {(.*?)}</script>', re.S)
    # result = re.findall(images_pattern,html)
    result = re.search(images_pattern, html)
    if result:
        first_content = result.group(1)
        result_pattern = re.compile('gallery: (.*?),\n', re.S)
        result_content = re.search(result_pattern, first_content)
        # 减去开头
        result_content_second = result_content.group(1)

        # 修改字符串
        result_content_second = result_content_second[12:]
        result_content_second = result_content_second[:-2]
        result_content_second = re.sub('\\\\', "", result_content_second)

        data = json.loads(result_content_second)
        if data and 'sub_images' in data.keys():
            sub_images = data['sub_images']
            images = [item['url'] for item in sub_images]
            # 下载图片
            for image in images:
                download_image(image)

            return {
                'title': title,
                'images': images,
                'url': url
            }


# 保存数据
def save_to_mongo(result):
    if db.MONGODB_COLLECTION.insert(result):
        print("插入数据成功")
        return True
    print("失败了")
    return False


# 下载数据
def download_image(url):
    print("正在下载。。。" + url)
    try:
        response = requests.get(url, headers=UserAgent.get_user_agent())
        if response.status_code == 200:
            # 二进制
            save_image(response.content)
        return None
    except RequestException:
        return None


# 将下载下来的内容存成图片  文件路径/文件名/后缀
# 1、拼接文件路径
# 2、判断是否存在文件路径
# 3、如果不存在，将数据写进去即可
def save_image(content):
    file_path = '{0}/{1}.{2}'.format("/Users/tsoumac2016/Desktop/Python实战项目/下载的街拍美图", md5(content).hexdigest(), 'jpg')
    if not os.path.exists(file_path):
        with open(file_path, 'wb') as f:
            f.write(content)
            f.close()


def main(offset, keywords):
    html = get_page(offset, keywords)
    json_page = parse_page_index(html)
    for item in json_page:
        # print(item)
        detail_html = get_page_detail(item.get('image'))
        if detail_html:
            result = parse_page_detail(detail_html, item.get('image'))
            print(result)
            if result:
                save_to_mongo(result)


if __name__ == '__main__':
    # start = time.time()
    # for i in range(0, 2):
    #     main(i * 20, KEYWORDS)
    # end = time.time()
    # print('用时为:  %s' %(end-start))

    start = time.time()
    pool = Pool(processes=8)
    for i in range(0, 1):
        pool.apply_async(main(i * 20, KEYWORDS))
    pool.close()
    pool.join()
    end = time.time()
    print('用时为:  %s' % (end - start))
