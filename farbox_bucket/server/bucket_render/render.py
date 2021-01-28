# coding: utf8
from __future__ import absolute_import
import os, io, re
from flask import abort, g
from jinja2.exceptions import TemplateNotFound

from farbox_bucket.utils import get_value_from_data
from farbox_bucket.bucket.utils import get_admin_bucket

from farbox_bucket.settings import STATIC_FILE_VERSION
from farbox_bucket.server.utils.request_path import get_request_path
from farbox_bucket.server.utils.site_resource import get_site_configs, has_template_by_name
from farbox_bucket.server.utils.response_html import insert_into_footer, insert_into_header



from farbox_bucket.server.template_system.env import farbox_bucket_env
from farbox_bucket.server.template_system.app_functions.after_request.cache_page import get_response_from_memcache
from farbox_bucket.server.template_system.api_template_render import render_api_template_as_response
from farbox_bucket.server.static.static_render import send_static_frontend_resource



from .static_file import render_as_static_resource_in_pages_for_farbox_bucket, render_as_static_file_for_farbox_bucket



def render_template_for_farbox_bucket(**kwargs):
    request_path = get_request_path()
    template_name = request_path.strip('/')
    if not template_name:
        template_name = 'index'
    try:
        template = farbox_bucket_env.get_template(template_name)
        html = template.render(**kwargs)
        html = re.sub(r'([ \t]*\n){10,}', '\n', html) # 去除多余的空行, 模板引擎造成的

        html = after_render_html(html)

        return html
    except TemplateNotFound as e:
        abort(404, 'not found for %s' % e.name)
    except Exception as e:
        raise e


def render_404_for_farbox_bucket():
    bucket = getattr(g, "bucket", None)
    if not bucket:
        return
    try:
        g.loads_in_page = []
        template = farbox_bucket_env.get_template("404")
        html = template.render()
        return html
    except:
        return





def render_bucket(bucket, web_path):
    g.bucket = bucket
    try: # memcache 的获取，也可能会出错, 概率很低
        cached_response = get_response_from_memcache()
        if cached_response:
            return cached_response
    except:
        pass
    if not web_path:
        web_path = get_request_path()

    # admin bucket 的默认主页对应
    if not web_path or web_path == "/":
        if bucket == get_admin_bucket() and not has_template_by_name("index"):
            return render_api_template_as_response("page_admin_default_homepage.jade")

    static_file_response = render_as_static_resource_in_pages_for_farbox_bucket(web_path)
    if not static_file_response and web_path.lstrip('/').startswith('template/'):
        # 对一些 template 目录下的兼容
        web_path_without_prefix = web_path.lstrip('/').replace('template/', '', 1)
        static_file_response = render_as_static_resource_in_pages_for_farbox_bucket(web_path_without_prefix)
    if static_file_response:
        return static_file_response
    else:
        file_response = render_as_static_file_for_farbox_bucket(web_path)
        if file_response:
            return file_response
        if web_path and '.' in web_path:
            static_response_from_system = send_static_frontend_resource(try_direct_path=True)
            if static_response_from_system:
                return static_response_from_system
        return render_template_for_farbox_bucket()



STATIC_FILE_VERSION_GET_VAR = '?version=%s' % STATIC_FILE_VERSION

############ for markdown scripts starts ############


mathjax_script = """
<script type= "text/javascript">
    window.MathJax = {
      tex: {
        inlineMath: [ ['$','$']],
        displayMath: [ ['$$','$$'] ]
      },
      svg: {fontCache: 'global'},
      startup: {
            ready: () => {
              MathJax.startup.defaultReady();
              MathJax.startup.promise.then(() => {
                if (typeof(send_to_app_client)!='undefined'){send_to_app_client({'action': 'start_to_export_pdf'})}
              });
            }
          },
      options: {
        renderActions: {
          addMenu: [0]
        }
      }
    };
</script>
<script type="text/javascript" src="/__lib/markdown_js/mathjax/tex-svg.js%s"></script>

""" % STATIC_FILE_VERSION_GET_VAR

echarts_script = '<script type="text/javascript" src="/__lib/markdown_js/echarts.min.js%s"></script>' % STATIC_FILE_VERSION_GET_VAR

mermaid_script = """'<script type="text/javascript" src="/__lib/markdown_js/mermaid/mermaid.min.js%s"></script>
<link rel="stylesheet" href="/__lib/markdown_js/mermaid/mermaid.css%s">
<script>mermaid.initialize({startOnLoad:true});</script>""" % (STATIC_FILE_VERSION_GET_VAR, STATIC_FILE_VERSION_GET_VAR)

def after_render_html(html):
    if '</body>' not in html:
        return html
    site_configs = get_site_configs()
    echarts = site_configs.get('echarts')
    mathjax = site_configs.get('mathjax')
    mermaid = site_configs.get('mermaid')
    if echarts:
        html = insert_into_header(echarts_script, html)
    if mathjax:
        html = insert_into_footer(mathjax_script, html)
    if mermaid:
        html = insert_into_footer(mermaid_script, html)
    inject_template = get_value_from_data(g, 'site.inject_template') or ''
    inject_template = inject_template.strip()
    if inject_template:
        html = html.replace('</body>', '\n%s\n</body>'%inject_template, 1)
    return html


############ for markdown scripts ends ############