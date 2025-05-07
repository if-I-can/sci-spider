import requests
import urllib.parse
import json
from impact_factor.core import Factor  # 导入影响因子查询工具


def test_headers_only(doi):
    encoded_doi = urllib.parse.quote(doi)
    api_urls = f"https://api.crossref.org/works?filter=has-full-text:true&mailto=1786293993@qq.com"

    try:
        response = requests.head(api_urls)
        if response.status_code == 200:
            print(response.headers)  # 仅返回响应的头部信息
        else:
            print(f"请求失败，状态码: {response.status_code}")
    except Exception as e:
        print(f"发生错误: {e}")


def title_doi_journal(keyword, rows):
    # 构建查询 URL，使用 query 参数根据关键词检索，并限制返回的文献数量
    api_url = f"https://api.crossref.org/works?query={keyword}&filter=has-full-text:true&rows={rows}&mailto=1786293993@qq.com"

    try:
        # 发送请求到 Crossref API
        response = requests.get(api_url)

        # 检查响应状态
        if response.status_code == 200:
            # 解析 JSON 响应
            data = response.json()

            # 提取文献信息
            works = data["message"].get("items", [])
            results = []
            for work in works:
                doi = work.get("DOI", "No DOI")
                journal = work.get("container-title", ["No journal"])[0]  # 获取期刊名称
                issn = work.get("ISSN", ["No ISSN"])[0]  # 获取期刊 ISSN
                results.append({
                    'doi': doi,
                    'journal': journal,
                    'issn': issn
                })
            print("Crossref 调用成功")
            return results
        else:
            print(f"Error: Received status code {response.status_code}")
            return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def fetch_impact_factor(issn):
    # 初始化影响因子查询工具
    fa = Factor()

    try:
        ak = fa.search(issn)
        factor = ak[0].get("factor")
        jcr = ak[0].get("jcr")
        return (factor, jcr)
    except Exception as e:
        print(f"获取影响因子时出错: {e}")
        return None


def get_dois_and_impact_factors(keyword, rows=100):
    # 获取 DOI 和 ISSN 信息
    doi_info = title_doi_journal(keyword, rows)
    print(doi_info)
    if not doi_info:
        print("未找到相关文献")
        return []

    # 存储结果：DOI, ISSN, 影响因子
    result_list = []

    # 查询每个 DOI 对应期刊的影响因子
    for entry in doi_info:
        issn = entry['issn']
        doi = entry['doi']

        # 获取影响因子
        impact_factors = fetch_impact_factor(issn)
        if impact_factors is None:
            continue  # 如果没有找到影响因子，则跳过当前条目
        else:
            result_list.append([doi, impact_factors[0], impact_factors[1]])

    return result_list


# 主函数
if __name__ == "__main__":
    # 你可以修改关键词来搜索不同的文献
    keyword = "Diseases of Rainbow Trout"

    # 获取 DOIs 和影响因子列表
    result = get_dois_and_impact_factors(keyword, rows=100)

    sorted_by_factor = sorted(result, key=lambda x: x[1], reverse=True)
    print(sorted_by_factor)

    # 按照分区排序 (从Q1到Q4，假设Q1为最高)
    sorted_by_jcr = sorted(result, key=lambda x: x[2])
    # print(result[0])
