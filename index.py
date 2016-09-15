import hashlib
import json
import os
import urlparse
import uuid

import wptserve

port = 8080
doc_root = './files/'
container_path = doc_root + 'annotations/'

per_page = 10

MEDIA_TYPE = 'application/ld+json; profile="http://www.w3.org/ns/anno.jsonld"'
# Prefer header variants
PREFER_MINIMAL_CONTAINER = "http://www.w3.org/ns/ldp#PreferMinimalContainer"
PREFER_CONTAINED_IRIS = "http://www.w3.org/ns/oa#PreferContainedIRIs"
PREFER_CONTAINED_DESCRIPTIONS = \
        "http://www.w3.org/ns/oa#PreferContainedDescriptions"


def extract_preference(prefer):
    """Extracts the parameters from a Prefer header's value
    >>> extract_preferences('return=representation;include="http://www.w3.org/ns/ldp#PreferMinimalContainer http://www.w3.org/ns/oa#PreferContainedIRIs"')
    {"return": "representation", "include": ["http://www.w3.org/ns/ldp#PreferMinimalContainer", "http://www.w3.org/ns/oa#PreferContainedIRIs"]}
    """
    obj = {}
    if prefer:
        params = prefer.split(';')
        for p in params:
            key, value = p.split('=')
            obj[key] = value.strip('"').split(' ')
    return obj


def dump_json(obj):
    return json.dumps(obj, indent=4, sort_keys=True)


def load_headers_from_file(path):
    headers = []
    with open(path) as header_file:
        data = header_file.read()
        headers = [tuple(item.strip() for item in line.split(":", 1))
                   for line in data.splitlines() if line]
    return headers


def annotation_files():
    files = []
    for file in os.listdir(container_path):
        if file.endswith('.jsonld') or file.endswith('.json'):
            files.append(file)
    return files


def annotation_iris(skip=0):
    iris = []
    for filename in annotation_files():
        iris.append('/annotations/' + filename)
    return iris[skip:][:per_page]


def annotations(skip=0):
    annotations = []
    files = annotation_files()
    for file in files:
        with open(container_path + file) as annotation:
            annotations.append(json.load(annotation))
    return annotations


def total_annotations():
    return len(annotation_files())


@wptserve.handlers.handler
def collection_get(request, response):
    """Annotation Collection handler. NOTE: This also routes paging requests"""

    # Paginate if requested
    qs = urlparse.parse_qs(request.url_parts.query)
    if 'page' in qs:
        return page(request, response)

    # stub collection
    collection_json = {
      "@context": [
        "http://www.w3.org/ns/anno.jsonld",
        "http://www.w3.org/ns/ldp.jsonld"
      ],
      "id": "/annotations/",
      "type": ["BasicContainer", "AnnotationCollection"],
      "total": 0,
      "label": "A Container for Web Annotations",
      "first": "/annotations/?page=0"
    }

    last_page = (total_annotations() / per_page) - 1
    collection_json['last'] = "/annotations/?page={0}".format(last_page)

    # Default Container format SHOULD be PreferContainedDescriptions
    preference = extract_preference(request.headers.get('Prefer'))
    if 'include' in preference:
        preference = preference['include']
    else:
        preference = None

    collection_json['total'] = total_annotations()
    # TODO: calculate last page and add it's page number

    if (qs.get('iris') and qs.get('iris')[0] is '1') \
            or (preference and PREFER_CONTAINED_IRIS in preference):
        return_iris = True
    else:
        return_iris = False

    # only PreferContainedIRIs has unqiue content
    if return_iris:
        collection_json['id'] += '?iris=1'
        collection_json['first'] += '&iris=1'
        collection_json['last'] += '&iris=1'

    if preference and PREFER_MINIMAL_CONTAINER not in preference:
        if return_iris:
            collection_json['first'] = annotation_iris()
        else:
            collection_json['first'] = annotations()

    collection_headers_file = doc_root + 'annotations/collection.headers'
    response.headers.update(load_headers_from_file(collection_headers_file))
    # this one's unique per request
    response.headers.set('Content-Location', collection_json['id'])
    return dump_json(collection_json)


@wptserve.handlers.handler
def collection_head(request, response):
    container_path = doc_root + request.request_path
    if os.path.isdir(container_path):
        response.status = 200
    else:
        response.status = 404

    headers_file = doc_root + 'annotations/collection.headers'
    for header, value in load_headers_from_file(headers_file):
        response.headers.append(header, value)

    response.content = None


@wptserve.handlers.handler
def collection_options(request, response):
    container_path = doc_root + request.request_path
    if os.path.isdir(container_path):
        response.status = 200
    else:
        response.status = 404

    response.headers.set('Access-Control-Allow-Origin', '*')
    response.content = None


def page(request, response):
    page_json = {
      "@context": "http://www.w3.org/ns/anno.jsonld",
      "id": "/annotations/",
      "type": "AnnotationPage",
      "partOf": {
        "id": "/annotations/",
        "total": 42023
      },
      "next": "/annotations/",
      "items": [
      ]
    }

    headers_file = doc_root + 'annotations/collection.headers'
    response.headers.update(load_headers_from_file(headers_file))

    qs = urlparse.parse_qs(request.url_parts.query)
    page_num = int(qs.get('page')[0])
    page_json['id'] += '?page={0}'.format(page_num)

    total = total_annotations()
    so_far = (per_page * (page_num+1))
    remaining = total - so_far

    if page_num != 0:
        page_json['prev'] = '/annotations/?page={0}'.format(page_num-1)

    page_json['partOf']['total'] = total

    if remaining > per_page:
        page_json['next'] += '?page={0}'.format(page_num+1)
    else:
        del page_json['next']

    if qs.get('iris') and qs.get('iris')[0] is '1':
        page_json['items'] = annotation_iris(so_far)
        page_json['id'] += '&iris=1'
        if 'prev' in page_json:
            page_json['prev'] += '&iris=1'
        if 'next' in page_json:
            page_json['next'] += '&iris=1'
    else:
        page_json['items'] = annotations(so_far)

    return dump_json(page_json)


@wptserve.handlers.handler
def annotation_get(request, response):
    """Individual Annotations"""
    requested_file = doc_root + request.request_path[1:]

    headers_file = doc_root + 'annotations/annotation.headers'
    response.headers.update(load_headers_from_file(headers_file))

    # Calculate ETag using Apache httpd's default method (more or less)
    # http://www.askapache.info//2.3/mod/core.html#fileetag
    statinfo = os.stat(requested_file)
    etag = "{0}{1}{2}".format(statinfo.st_ino, statinfo.st_mtime,
                              statinfo.st_size)
    # obfuscate so we don't leak info; hexdigest for string compatibility
    response.headers.set('Etag', hashlib.sha1(etag).hexdigest())

    if os.path.isfile(requested_file):
        with open(requested_file) as data_file:
            data = data_file.read()
        return data
    else:
        return (404, [], 'Not Found')


@wptserve.handlers.handler
def annotation_head(request, response):
    requested_file = doc_root + request.request_path[1:]
    headers_file = doc_root + 'annotations/annotation.headers'
    if os.path.isfile(requested_file):
        response.status = 200
    else:
        response.status = 404

    headers = load_headers_from_file(headers_file)
    for header, value in headers:
        response.headers.append(header, value)
    response.content = None


@wptserve.handlers.handler
def annotation_options(request, response):
    requested_file = doc_root + request.request_path[1:]
    if os.path.isfile(requested_file):
        response.status = 200
    else:
        response.status = 404

    response.headers.set('Access-Control-Allow-Origin', '*')
    response.content = None


def create_annotation(body):
    # TODO: verify media type is JSON of some kind (at least)
    incoming = json.loads(body)
    id = str(uuid.uuid4())
    if 'id' in incoming:
        incoming['canonical'] = incoming['id']
    incoming['id'] = '/annotations/' + id

    with open(container_path + id, 'w') as outfile:
        json.dump(incoming, outfile)

    return incoming


@wptserve.handlers.handler
def annotation_post(request, response):
    incoming = create_annotation(request.body)
    # TODO: rashly assuming the above worked...of course
    return (201,
            [('Content-Type', MEDIA_TYPE), ('Location', incoming['id'])],
            dump_json(incoming))


@wptserve.handlers.handler
def annotation_put(request, response):
    incoming = create_annotation(request.body)
    return (200,
            [('Content-Type', MEDIA_TYPE), ('Location', incoming['id'])],
            dump_json(incoming))


@wptserve.handlers.handler
def annotation_delete(request, response):
    requested_file = doc_root + request.request_path[1:]
    try:
        os.remove(requested_file)
        return (204, [], '')
    except OSError:
        return (404, [], 'Not Found')


if __name__ == '__main__':
    print 'http://localhost:{0}/'.format(port)

    routes = [
        ("GET", "", wptserve.handlers.file_handler),
        ("GET", "index.html", wptserve.handlers.file_handler),

        # container/collection responses
        ("HEAD", "annotations/", collection_head),
        ("OPTIONS", "annotations/", collection_options),
        ("GET", "annotations/", collection_get),

        # create annotations in the collection
        ("POST", "annotations/", annotation_post),

        # single annotation responses
        ("HEAD", "annotations/*", annotation_head),
        ("OPTIONS", "annotations/*", annotation_options),
        ("GET", "annotations/*", annotation_get),
        ("PUT", "annotations/*", annotation_put),
        ("DELETE", "annotations/*", annotation_delete)
    ]

    httpd = wptserve.server.WebTestHttpd(port=port, doc_root=doc_root,
                                         routes=routes)
    httpd.start(block=True)
