# coding: utf8
from flask import g, abort

from farbox_bucket.utils import smart_unicode
from farbox_bucket.utils.functional import cached_property
from farbox_bucket.utils import get_value_from_data, to_int
from farbox_bucket.server.utils.site_resource import get_site_config
from farbox_bucket.server.utils.record_and_paginator.paginator import auto_pg
from farbox_bucket.server.utils.cache_for_function import cache_result
from farbox_bucket.server.utils.request_path import get_request_offset_path_without_prefix, get_request_path_without_prefix
from farbox_bucket.server.utils.request_path import auto_bucket_url_path
from farbox_bucket.server.template_system.api_template_render import render_api_template

from farbox_bucket.bucket.utils import get_bucket_files_info
from farbox_bucket.bucket.record.get.mix import mix_get_record_paths
from farbox_bucket.bucket.record.get.folder import get_folder_records
from farbox_bucket.bucket.record.get.path_related import get_record_by_path, get_record_by_url, get_records_by_paths, get_next_record
from farbox_bucket.bucket.record.get.tag_related import get_records_by_tag

from farbox_bucket.server.utils.record_and_paginator.paginator import get_paginator

from farbox_bucket.server.template_system.model.category import get_record_parent_category, Category




class Posts(object):
    def __init__(self):
        self.pager_name = 'posts'
        self.min_per_page = 0


    def __iter__(self):
        # 返回一个迭代器，用于 for 的命令
        obj = self.list_obj
        if hasattr(obj, '__iter__'):
            return obj.__iter__()
        return obj

    def get_recent(self, limit=8):
        limit = to_int(limit, 8)
        limit = min(100, limit)
        post_paths = self._post_paths[:limit*2] # 取 2 倍，如果有非 public 的比较多，可能会不准确
        post_docs = get_records_by_paths(self.bucket, post_paths, ignore_marked_id=True, limit=limit)
        return post_docs
        #return get_data(type='post', limit=limit, sort='-date', with_page=False)

    def get_recent_posts(self, limit=8):
        return self.get_recent(limit)


    def get_posts_by_tag(self, tag, sort_by='-date'):
        return get_records_by_tag(self.bucket, tag, sort_by=sort_by)


    @cached_property
    def _post_paths(self):
        paths = mix_get_record_paths(bucket=self.bucket, data_type='post', data_type_reverse_sort=True)
        return paths

    @cached_property
    def length(self):
        return len(self.list_obj)

    @cached_property
    def bucket(self):
        return getattr(g, 'bucket', None)

    @property
    def pager(self):
        # 由于获得分页的数据对象
        # 比如可以直接调用  posts.pager....
        return get_paginator(self.pager_name, match_name=True)

    @cached_property
    def list_obj(self):
        pager_name = self.pager_name

        if self.request_path.startswith('/category/'):  # 指定目录下的
            category_path = get_request_offset_path_without_prefix(1)
            records = auto_pg(bucket=self.bucket, data_type='post', pager_name=pager_name, path=category_path,
                              ignore_marked_id=True, prefix_to_ignore='_', sort_by='-date', min_limit=self.min_per_page)
            return records

        if self.request_path.startswith('/tags/') or self.request_path.startswith('/tag/'):
            _tags = get_request_offset_path_without_prefix(offset=1).strip('/')
            _tags = [tag for tag in _tags.split('+') if tag]
            records = get_records_by_tag(self.bucket, tag=_tags, sort_by='-date')
            return records

        # 默认不输出非 public 的日志
        records = auto_pg(bucket=self.bucket, data_type='post', pager_name=pager_name,
                          ignore_marked_id=True, prefix_to_ignore='_', sort_by='-date', min_limit=self.min_per_page)
        return records

    @cached_property
    def request_path(self):
        return get_request_path_without_prefix()

    @cached_property
    def bucket(self):
        bucket = getattr(g, 'bucket', None)
        return bucket


    @cached_property
    def categories(self):
        # todo 处理 categories 的逻辑
        return []


    def get_post_by_url(self, url=''):
        if not self.bucket or not url:
            return None
        return get_record_by_url(self.bucket, url)


    def get_post_by_path(self, path=''):
        if not self.bucket or not path:
            return None
        return get_record_by_path(self.bucket, path)

    def get_one(self, path=None, url=None):
        if path:
            return self.get_post_by_path(path)
        else:
            return self.get_post_by_url(url)

    def find_one(self, path=None, url=None):
        return self.find_one(path=path, url=url)

    def get_current_post(self, auto_raise_404=False):
        # 在 functions.namespace.shortcut 中，将 post 本身作为一个快捷调用，可以直接调用
        doc_in_g = getattr(g, 'doc', None)
        if doc_in_g and isinstance(doc_in_g, dict) and doc_in_g.get('type') == 'post':
            return doc_in_g

        # 得到当前 url 下对应的 post
        hide_post_prefix = get_site_config('hide_post_prefix', default_value=False)
        if hide_post_prefix:  # 不包含 /post/ 的 url
            url_path = self.request_path.lstrip('/')
        else:  # 可能是/post/<url>的结构
            url_path = get_request_offset_path_without_prefix(offset=1)
        post_doc = self.get_post_by_url(url_path)

        if not post_doc and url_path and '/' in url_path:  # sub path 的对应，offset 一次，让 markdown 本身作为 template 成为可能
            url_path = '/'.join(url_path.split('/')[:-1])
            post_doc = self.get_post_by_url(url_path)

        if post_doc:  # 写入g.doc，作为上下文对象参数来处理
            g.doc = post_doc
        else:
            if auto_raise_404:
                abort(404, 'can not find the matched post')
        return post_doc

    @cached_property
    def counts(self):
        self_list_obj = self.list_obj  # 先行调用
        if self.pager:
            return self.pager.total_count
        else:
            # /tag/ 下直接获取，没有分页的逻辑
            if self.list_obj:
                return len(self.list_obj)
            else:
                return   0


    @cached_property
    def post(self):
        return self.get_current_post(auto_raise_404=False)

    @cached_property
    def post_with_404(self):
        return self.get_current_post(auto_raise_404=True)

    @cached_property
    def next_one(self):
        record = get_next_record(bucket=self.bucket, current_record=self.post, reverse=True)
        return record

    @cached_property
    def previous_one(self):
        record = get_next_record(bucket=self.bucket, current_record=self.post, reverse=False)
        return record

    @cached_property
    def pre_one(self):
        return self.previous_one


    @cached_property
    def category(self):
        # /xxx/<category_path>
        # 根据路径，获得当前的 category 对象
        if self.request_path == '/':
            return None
        parent_path = get_request_offset_path_without_prefix(offset=1)
        return Category(parent_path)
        #return get_record_parent_category(self.post)


    @cached_property
    def categories(self):
        category_records = get_folder_records(self.bucket)
        cats = []
        for record in category_records:
            cats.append(Category(record))
        return cats


    def get_tag_url(self, tag):
        if isinstance(tag, (list, tuple)):
            tag = '+'.join(tag)
        url = '/tag/%s' % smart_unicode(tag)
        return auto_bucket_url_path(url)

    def tag_url(self, tag):
        return self.get_tag_url(tag)


    def set_min_per_page(self, min_per_page):
        if isinstance(min_per_page, int) and min_per_page >= 0:
            self.min_per_page = min_per_page
        return ''  # return nothing


    def search_in_html(self, base_url='', under='', just_js=False, **kwargs):
        # 产生搜索的HTML代码片段
        return render_api_template('search_posts.jade', search_base_url=base_url,
                                    search_under=under, just_js=just_js, **kwargs)


@cache_result
def posts():
    return Posts()


@cache_result
def post():
    posts_namespace = posts()
    return posts_namespace.post # post_with_404