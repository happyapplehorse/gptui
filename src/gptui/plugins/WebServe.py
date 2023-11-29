import itertools
import json
import logging

import chardet
import httpx
from lxml import html
from semantic_kernel.orchestration.sk_context import SKContext
from semantic_kernel.skill_definition import sk_function, sk_function_context_parameter

from gptui.gptui_kernel.manager import auto_init_params
from gptui.models.utils.config_from_dot_env import config_from_dot_env


gptui_logger = logging.getLogger("gptui_logger")


class WebServe:
    def __init__(self, manager):
        self.manager = manager

    @auto_init_params("0")
    @classmethod
    def get_init_params(cls, manager) -> tuple:
        return (manager,)

    @sk_function(
        description="Searching for information on the Internet through Google",
        name="google_search",
    )
    @sk_function_context_parameter(
        name="query",
        description="The keywords to search",
    )
    @sk_function_context_parameter(
        name="num",
        description="Number of search results to return. Valid values are integers between 1 and 10, inclusive",
    )
    @sk_function_context_parameter(
        name="start",
        description=("The index of the first result to return. The default number of results per page is 10, "
                     "so &start=11 would start at the top of the second page of results. Notice: start + num have to be less than 100."),
        default_value="1",
    )
    def google_search(self, context: SKContext) -> str:
        """
        {"status_codes":status_codes, "query": query, "reslut_list":[{result}]}
        status_codes:
            901: internet react error
            902: search empty
            903: input parameters error
        """
        config = config_from_dot_env(self.manager.dot_env_config_path)
        google_key = config.get("GOOGLE_KEY")
        cx = config.get("GOOGLE_CX")
        assert google_key is not None and cx is not None
        url = 'https://www.googleapis.com/customsearch/v1'
        
        query = context["query"]
        num = int(context["num"])
        start = int(context["start"])
        result_metadata = {"status_codes":None, "query":query, "result_list":[]}
        
        if not query:
            result_metadata["status_codes"] = 902
            return json.dumps(result_metadata, ensure_ascii=False)
        if (not 1 <= num <= 10) or start < 0 or num + start > 100:
            result_metadata["status_codes"] = 903
            return json.dumps(result_metadata, ensure_ascii=False)

        parameters = {
                "key": google_key,
                "cx": cx,
                "q": query,
                "num": num,
                "start": start,
                }
        try:
            with httpx.Client() as client:
                response = client.request("GET", url = url, params = parameters)
            results = response.json()
        except:
            result_metadata["status_codes"] = 901
            return json.dumps(result_metadata, ensure_ascii=False)
        else:
            result_metadata["status_codes"] = response.status_code
            if response.status_code == 200:
                for item in results['items']:
                    result_metadata["result_list"].append({"title":item["title"], "url":item["link"], "snippet":item["snippet"]})
            
            # result = json.dumps(result_metadata, ensure_ascii=False)
            # to format
            result_list = result_metadata["result_list"]
            content = f'Folllwing are the search results of "{query}":\n'
            for i, result in enumerate(result_list):
                content += f'{i+1}.\n'
                content += 'Title: ' + result["title"] + '\n'
                content += 'Snippet: ' + result["snippet"] + '\n'
                content += 'URL: ' + result["url"] + '\n\n'
            return content

    @sk_function(
        description="Get the text content of given webpage's url",
        name="web_parse",
    )
    @sk_function_context_parameter(
        name="url",
        description="The url of webpage",
    )
    @sk_function_context_parameter(
        name="table",
        description="True or False, indicate whether a table in html should be parsed",
        default_value="False"
    )
    def web_parse(self, context: SKContext) -> str:
        """Extract the title, if present.
        Extract all p paragraphs, various levels of subheadings, ordered lists, unordered lists, tables, and horizontal rules.
        """
        
        url = context["url"]
        ul = True
        ol = True
        dl = True
        table = bool(context["table"])
        title = True
        start_with_h = True
        a_href = True
        br = True
        blockquote = True
        img = False

        etree = html.etree
        
        def is_descendant(child, ancestor_check: list) -> bool:
            ancestor_list = child.xpath("./ancestor::*")
            for ancestor in ancestor_check:
                if ancestor in ancestor_list:
                    return True
            return False

        def p_get(p) -> str:
            text = '\n'
            all_node = p.xpath("./node()")
            i = 0
            for content in all_node:
                i += 1
                if isinstance(content, str):
                    if content.strip():
                        text += content.strip()
                elif content in node_get(p):
                    txt = content_get_iterable_distribute(content)
                    if i == 1:
                        if txt.startswith('\n'):
                            text += txt[1:]
                        else:
                            text += txt
                else:
                    text += ''.join(content.xpath(".//text()"))
            return text
        def ul_get(ul) -> str:
            text = '\n'
            item_list = ul.xpath("./li")
            for item in item_list:
                text += u'\u2022   '
                i = 0
                for content in node_get(item):
                    i += 1
                    if isinstance(content, str):
                        if content.strip():
                            text += content.strip()
                    else:
                        txt = content_get_iterable_distribute(content)
                        if i == 1:
                            if txt.startswith('\n'):
                                text += txt[1:]
                            else:
                                text += txt
                        else:
                            if txt.startswith('\n'):
                                text += '\n    ' + txt[1:]
                            else:
                                text += txt
                text += '\n'
            return text[:-1]
        def ol_get(ol) -> str:
            text = '\n'
            item_list = ol.xpath("./li")
            num = 1
            for item in item_list:
                text += f'{num}.  '
                i = 0
                for content in node_get(item):
                    i += 1
                    if isinstance(content, str):
                        if content.strip():
                            text += content.strip()
                    else:
                        txt = content_get_iterable_distribute(content)
                        if i == 1:
                            if txt.startswith('\n'):
                                text += txt[1:]
                            else:
                                text += txt
                        else:
                            if txt.startswith('\n'):
                                text += '\n    ' + txt[1:]
                            else:
                                text += txt
                num += 1
                text += '\n'
            return text[:-1]
        def dl_get(dl) -> str:
            text = '\n'
            item_list = dl.xpath("./*[name() = 'dt' or name() = 'dd']")
            for item in item_list:
                if item.tag == 'dt':
                    i = 0
                    for content in node_get(item):
                        i += 1
                        if isinstance(content, str):
                            if content.strip():
                                text += content.strip()
                        else:
                            txt = content_get_iterable_distribute(content)
                            if i == 1:
                                if txt.startswith('\n'):
                                    text += txt[1:]
                                else:
                                    text += txt
                            else:
                                text += txt
                    text += '\n'
                elif item.tag == 'dd':
                    i = 0
                    for content in node_get(item):
                        i += 1
                        if isinstance(content, str):
                            if content.strip():
                                text += '    ' + content.strip()
                        else:
                            txt = content_get_iterable_distribute(content)
                            if i == 1:
                                if txt.startswith('\n'):
                                    text += '    ' + txt[1:]
                                else:
                                    text += '    ' + txt
                            else:
                                if txt.startswith('\n'):
                                    text += '\n    ' + txt[1:]
                                else:
                                    text += txt
                    text += '\n'
            return text[:-1]
        def table_get(table) -> str:
            text = '\n(Following is a table in MarkDown type:)\n'
            caption = table.xpath(".//caption")
            if caption:
                text += 'Caption:  ' + ''.join(caption[0].xpath("./text()")) + '\n'
            th_list = table.xpath(".//tr/th")
            text += '|'
            for item in th_list:
                text += ' ' + ''.join(item.xpath("./text()")) + ' |'
            text += '\n'
            text += '|---' * len(th_list) + '|\n'
            item_list = table.xpath(".//tr/td/..")
            for item in item_list:
                text += '|'
                for content in item.xpath("./td"):
                    for cont in node_get(content):
                        if isinstance(cont, str):
                            if cont.strip():
                                text += ' ' + cont.strip()
                        else:
                            txt = content_get_iterable_distribute(content)
                            if txt.startswith('\n'):
                                text += ' ' + txt[1:]
                            else:
                                text += ' ' + txt
                    text += ' |'
                text += '\n'
            return text[:-1]
        def h_get(h) -> str:
            text = '\n'
            i = 0
            for content in node_get(h):
                i += 1
                if isinstance(content, str):
                    if content.strip():
                        text += content.strip()
                else:
                    txt = content_get_iterable_distribute(content)
                    if i == 1:
                        if txt.startswith('\n'):
                            text += txt[1:]
                        else:
                            text += txt
                    else:
                        text += txt
            return text
        def a_get(a) -> str:
            text = ''
            for content in node_get(a):
                if isinstance(content, str):
                    if content.strip():
                        text += content.strip()
                else:
                    txt = content_get_iterable_distribute(content)
                    if txt.startswith('\n'):
                        text += txt[1:]
                    else:
                        text += txt
            text += f'{a.xpath("@href")}'
            return text
        def img_get(img) -> str:
            text = '\n[This is a image:  '
            if img.xpath("./@title"):
                text += 'title = ' + ''.join(img.xpath("./@title")) + '  '
            text += '{url = ' + ''.join(img.xpath("./@src")) + '}]'
            return text
        def blockquote_get(blockquote) -> str:
            text = '\n'
            i = 0
            for content in node_get(blockquote):
                i += 1
                if isinstance(content, str):
                    if content.strip():
                        text += content.strip()
                else:
                    txt = content_get_iterable_distribute(content)
                    if i == 1:
                        if txt.startswith('\n'):
                            text += txt[1:]
                        else:
                            text += txt
                    else:
                        text += txt
            return text
        def span_get(span) -> str:
            return '' + ''.join(span.xpath(".//text()"))
        
        def node_get(node):
            "include the text in the node itself by name()=''"
            content_list = node.xpath("./node()[name() = '' or name() = 'p' or name() = 'ul' or name() = 'ol' or name() = 'dl' or name() = 'blockquote' \
                    or name() = 'table' or name() = 'title' or starts-with(name(),'h') or (name() = 'a' and @href) or name() = 'img' or name() = 'br' or name() = 'span']")
            return content_list
        
        def content_get_iterable_distribute(content) -> str:
            if content.tag == "title":
                return h_get(content)
            elif content.tag in ['h1','h2','h3','h4','h5','h6']:
                return h_get(content)
            elif content.tag == "p":
                return p_get(content)
            elif content.tag == "ul":
                return ul_get(content)
            elif content.tag == "ol":
                return ol_get(content)
            elif content.tag == "dl":
                return dl_get(content)
            elif content.tag == "table":
                return table_get(content)
            elif content.tag == "a":
                return a_get(content)
            elif content.tag == 'hr' or content.tag == 'br':
                return '\n'
            elif content.tag == 'img':
                return img_get(content)
            elif content.tag == 'blockquote':
                return blockquote_get(content)
            elif content.tag == 'span':
                return span_get(content)
            else:
                return ''

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36 Edg/111.0.1661.54'
                }
        
        # auto detect the character set
        def autodetect(content):
            return chardet.detect(content).get("encoding")

        result = {"status_code":None, "url":url, "web_text":''}
        
        try:
            with httpx.Client(default_encoding = autodetect) as client:
                response = client.request("GET", url = url, headers = headers, follow_redirects = True)
            page_text = response.text
        except:
            result["status_code"] = 901
            return json.dumps(result, ensure_ascii=False)
        else:
            tree = etree.HTML(page_text)
            xpath_str = "//p/..//*[name() = 'p'"
            if ul:
                xpath_str += " or name() = 'ul'"
            if ol:
                xpath_str += " or name() = 'ol'"
            if dl:
                xpath_str += " or name() = 'dl'"
            if table:
                xpath_str += " or name() = 'table'"
            if title:
                xpath_str += " or name() = 'title'"
            if start_with_h:
                xpath_str += " or starts-with(name(),'h')"
            if a_href:
                xpath_str += " or (name() = 'a' and @href)"
            if br:
                xpath_str += " or name() = 'br'"
            if blockquote:
                xpath_str += " or name() = 'blockquote'"
            if img:
                xpath_str += " or name() = 'img'"
            xpath_str += "]"
            content_list = tree.xpath(xpath_str)
            #content_list = tree.xpath("//p/..//*[name() = 'p' or name() = 'ul' or name() = 'ol' or name() = 'dl' or name() = 'table' \
            #    or name() = 'title' or starts-with(name(),'h') or (name() = 'a' and @href) or name() = 'br' or name() = 'blockquote' or name() = 'img']"
            #)
            text_list = []
            already_traversed_list = []
            for content in content_list:
                if is_descendant(content, already_traversed_list):
                    continue
                text_list.append(content_get_iterable_distribute(content))
                already_traversed_list.append(content)
            result["status_code"] = response.status_code
            result["web_text"] = ''.join(list(itertools.chain(*text_list)))
            return json.dumps(result, ensure_ascii=False)
