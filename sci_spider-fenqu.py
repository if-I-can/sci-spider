"""
SCI-HUB论文下载工具
Author: Xu Chenchen (Modified)
功能：根据关键词从Crossref获取DOI，然后从sci-hub下载对应的PDF文件
"""
import os
import re
import json
import time
import requests
import urllib.parse
from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse
from typing import Optional, Dict, List
from lxml.html import fromstring
from jcr_list import get_dois_and_impact_factors


# ================ 文件名处理 ================
def get_valid_filename(filename: str, name_len: int = 128) -> str:
    """生成合法的文件名"""
    return re.sub(r'[^0-9A-Za-z\-,._;]', '_', filename)[:name_len]


# ================ 缓存处理 ================

class Cache:
    def __init__(self, cache_dir: str):
        self.cache_dir = cache_dir
        self.cache = self.read_cache()

    def __getitem__(self, url: str) -> Optional[str]:
        return self.cache.get(url)

    def __setitem__(self, key: str, value: str):
        """保存数据到缓存"""
        self.cache[key] = value
        try:
            with open(self.cache_dir, 'w', encoding='utf-8') as fp:
                json.dump(self.cache, fp, indent=2)
        except Exception as e:
            print(f'缓存写入错误: {e}')

    def read_cache(self) -> dict:
        """从磁盘加载缓存"""
        try:
            if os.path.exists(self.cache_dir):
                if os.path.getsize(self.cache_dir):
                    with open(self.cache_dir, 'r', encoding='utf-8') as fp:
                        return json.load(fp)
            with open(self.cache_dir, 'w', encoding='utf-8'):
                return {}
        except Exception as e:
            print(f'缓存读取错误: {e}')
            return {}


# ================ HTML解析 ================
def get_link_xpath(html: str) -> Optional[Dict]:
    """使用xpath解析sci-hub页面获取下载链接"""
    try:
        tree = fromstring(html)
        a = tree.xpath('//div[@id="buttons"]/button')
        if len(a) == 0:
            a = tree.xpath('//div[@id="buttons"]/ul/li/a')

        if len(a) == 0:
            print('抱歉，sci-hub暂未收录此文章。')
            return None

        for a_unit in a:
            onclick = a_unit.get('onclick')
            if onclick:
                break

        onclick = re.findall(r"location.href\s*=\s*'(.*?)'", onclick)[0]
        title = tree.xpath('//div[@id="citation"]/i/text()')
        if len(title) == 0:
            title = tree.xpath('//div[@id="citation"]/text()')
        return {'title': title[0], 'onclick': onclick}
    except Exception as e:
        print(f'解析错误: {e}')
        return None


# ================ 下载功能 ================
def doi_parser(doi: str, start_url: str, useSSL: bool = True) -> str:
    """将DOI转换为URL"""
    protocol = 'https' if useSSL else 'http'
    return f"{protocol}://{start_url}/{doi}"


def get_robot_parser(robot_url: str) -> Optional[RobotFileParser]:
    """获取robots.txt解析器"""
    try:
        rp = RobotFileParser()
        rp.set_url(robot_url)
        rp.read()
        return rp
    except Exception as e:
        print(f'robots.txt解析错误: {e}')
        return None


def wait(url: str, delay: int = 3, domains: dict = None) -> None:
    """控制下载间隔"""
    if domains is None:
        domains = {}
    domain = urlparse(url).netloc
    last_accessed = domains.get(domain)
    if delay > 0 and last_accessed is not None:
        sleep_secs = delay - (time.time() - last_accessed)
        if sleep_secs > 0:
            time.sleep(sleep_secs)
    domains[domain] = time.time()


def download(url: str, headers: dict, proxies: dict = None, num_retries: int = 2) -> Optional[str]:
    """下载网页内容"""
    print(f'正在下载页面: {url}')
    try:
        response = requests.get(url, headers=headers, proxies=proxies, verify=False)
        if response.status_code >= 400:
            if num_retries and 500 <= response.status_code < 600:
                return download(url, headers, proxies, num_retries - 1)
            print(f'下载失败，状态码: {response.status_code}')
            return None
        return response.text
    except requests.exceptions.RequestException as e:
        print(f'下载错误: {e}')
        return None


def download_pdf(result: Dict, headers: dict, dir: str, proxies: dict = None,
                 num_retries: int = 2, doi: str = None) -> bool:
    """下载PDF文件"""
    url = result['onclick']
    if not urlparse(url).scheme:
        url = f'https:{url}'
    url = url.replace('\\', '')

    print(f'正在下载文件: {url}')
    try:
        response = requests.get(url, headers=headers, proxies=proxies, verify=False)
        if response.status_code >= 400:
            if num_retries and 500 <= response.status_code < 600:
                return download_pdf(result, headers, dir, proxies, num_retries - 1, doi)
            print(f'文件下载失败，状态码: {response.status_code}')
            return False

        filename = get_valid_filename(result['title'] if len(result['title']) >= 5 else doi) + '.pdf'
        path = os.path.join(dir, filename)

        with open(path, 'wb') as fp:
            fp.write(response.content)
        print(f'文件已保存: {path}')
        return True
    except requests.exceptions.RequestException as e:
        print(f'文件下载错误: {e}')
        return False


# ================ Crossref API ================
def get_dois_from_crossref(keyword: str, rows: int = 100) -> list:
    """从Crossref获取DOI列表"""
    api_url = f"https://api.crossref.org/works?query={urllib.parse.quote(keyword)}&filter=has-full-text:true&rows={rows}&mailto=1786293993@qq.com"

    try:
        response = requests.get(api_url, timeout=30)
        response.raise_for_status()
        data = response.json()
        works = data["message"].get("items", [])
        doi_list = [work.get("DOI") for work in works if work.get("DOI")]
        return doi_list
    except Exception as e:
        print(f"获取DOI列表时出错: {e}")
        return []


# ================ 主要功能 ================
def sci_hub_crawler(doi_list: List[str], dir: str, robot_url: str = None,
                    user_agent: str = 'sheng', proxies: dict = None,
                    num_retries: int = 2, delay: int = 3,
                    start_url: str = 'www.sci-hub.wf',
                    useSSL: bool = True, nolimit: bool = False,
                    cache: Cache = None) -> None:
    """下载指定DOI列表的论文"""
    headers = {'User-Agent': user_agent}
    protocol = 'https' if useSSL else 'http'

    if not robot_url:
        robot_url = f"{protocol}://{start_url}/robots.txt"

    rp = get_robot_parser(robot_url)
    domains = {}
    download_succ_cnt = 0

    os.makedirs(dir, exist_ok=True)
    for q in ['Q1', 'Q2', 'Q3', 'Q4']:
        os.makedirs(os.path.join(dir, q), exist_ok=True)

    print('开始遍历DOI列表...')
    for doi in doi_list:
        url = doi_parser(doi[0], start_url, useSSL)

        if cache and cache[url]:
            print(f'已下载过: {cache[url]}')
            download_succ_cnt += 1
            continue

        if rp and rp.can_fetch(user_agent, url) or nolimit:
            wait(url, delay, domains)
            html = download(url, headers, proxies, num_retries)
            result = get_link_xpath(html)

            if result:
                # 根据 doi[2] 的值选择子目录
                quartile = doi[2]  # doi[2] 应该是 'Q1', 'Q2', 'Q3', 'Q4' 中的一个
                target_dir = os.path.join(dir, quartile)

                if download_pdf(result, headers, target_dir, proxies, num_retries, doi):
                    if cache:
                        cache[url] = f'https:{result["onclick"]}'
                    download_succ_cnt += 1
        else:
            print(f'被robots.txt拦截: {url}')

    print(f'下载完成：共{len(doi_list)}篇文献，成功下载{download_succ_cnt}篇')

    print(f'下载完成：共{len(doi_list)}篇文献，成功下载{download_succ_cnt}篇')


def sci_spider(keyword: str, dir: str = './downloaded_papers',
               robot_url: str = None, user_agent: str = 'sheng',
               proxies: dict = None, num_retries: int = 2,
               delay: int = 3, start_url: str = 'www.sci-hub.wf',
               useSSL: bool = True, nolimit: bool = False,
               cache: Cache = None) -> None:
    """主函数：根据关键词搜索并下载论文"""
    print('正在收集DOI列表...')
    # doi_list = get_dois_from_crossref(keyword, rows=100)
    doi_list = get_dois_and_impact_factors(keyword, rows=100)  # 得到 doi 列表
    doi_list_sort_jcr = sorted(doi_list, key=lambda x: x[2])
    # doi_list_sort_jcr = sorted(doi_list, key=lambda x: x[2])
    # doi_list_sort_factor = sorted(doi_list, key=lambda x: x[1])
    if not doi_list:
        print('DOI列表为空，爬取终止...')
        return

    print(f'DOI收集成功，共找到 {len(doi_list)} 篇文献')
    print('正在从sci-hub下载PDF文件...')

    os.makedirs(dir, exist_ok=True)

    try:
        sci_hub_crawler(doi_list_sort_jcr, dir, robot_url, user_agent, proxies,
                        num_retries, delay, start_url, useSSL, nolimit, cache)
        print('下载完成！')
    except Exception as e:
        print(f'下载过程中出现错误: {e}')


if __name__ == '__main__':
    # 禁用SSL警告
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    start = time.time()

    # 设置参数
    keyword = "rainbow trout and density"
    save_dir = f"/home/star/3.8t_1/Workspace/wch/new/bake/zsl1/Agent/rainbow trout/{keyword}"  # 文件保存目录
    cache_dir = f"/home/star/3.8t_1/Workspace/wch/new/bake/zsl1/Agent/rainbow trout/{keyword}/cache.txt"  # 缓存路径
    start_url = 'www.sci-hub.se'  # 或 'www.sci-hub.wf'

    # 创建缓存对象
    cache = Cache(cache_dir)

    # 执行爬取
    try:
        sci_spider(keyword, dir=save_dir, start_url=start_url, nolimit=True, cache=cache)
    except Exception as e:
        print(f'程序执行出错: {e}')

    print('总耗时: %ds' % (time.time() - start))