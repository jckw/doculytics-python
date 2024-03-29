from flask import Flask, request, Response
import requests
from bs4 import BeautifulSoup
import urllib.parse
import logging
import pprint

app = Flask(__name__)

# The target URL or domain you're proxying
target_url = "https://jackwxyz.notion.site"
proxy_url = "http://127.0.0.1:5000"  # Your proxy's address

# Configure logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def proxy(path):
    global target_url
    url = urllib.parse.urljoin(target_url, path)

    # Include original request headers in the proxy request
    headers = {key: value for key, value in request.headers if key != "Host"}
    headers["Host"] = urllib.parse.urlparse(target_url).netloc
    headers["Origin"] = target_url
    headers["Referer"] = target_url

    pprint.pprint(
        [
            url,
            headers,
            request.args,
            request.cookies,
        ]
    )

    # Send request to the target server
    if request.method == "GET":
        resp = requests.get(
            url,
            headers=headers,
            params=request.args,
            cookies=request.cookies,
        )
    elif request.method == "POST":
        resp = requests.post(
            url,
            headers=headers,
            params=request.args,
            cookies=request.cookies,
            data=request.form,
        )
    else:
        raise ValueError(f"Unsupported HTTP method: {request.method}")

    excluded_headers = [
        "content-encoding",
        "content-length",
        "transfer-encoding",
        "connection",
    ]
    headers = [
        (name, value)
        for (name, value) in resp.raw.headers.items()
        if name.lower() not in excluded_headers
    ]

    # Logging the request
    logging.info(f"Request: {request.method} {path}")
    if resp.status_code != 200:
        logging.warning(f"Response: {resp.status_code} for {path}")

    # Handle content rewriting and cookie forwarding for HTML responses
    content_type = resp.headers.get("Content-Type", "")

    if "html" in content_type:
        soup = BeautifulSoup(resp.content, "html.parser")
        # Rewrite URLs in various tags
        for tag in soup.find_all(["a", "link", "script", "img", "form"]):
            for attr in ["href", "src", "action"]:
                if tag.has_attr(attr):
                    original = tag[attr]
                    if not urllib.parse.urlparse(
                        original
                    ).netloc:  # Check if URL is relative
                        # Rewrite the URL to go through the proxy
                        new_url = urllib.parse.urljoin(proxy_url, original)
                        tag[attr] = new_url

        # Adjust the base tag or add one if it doesn't exist
        base = soup.find("base")
        if not base:
            base = soup.new_tag("base", href=proxy_url)
            soup.head.insert(0, base)
        else:
            base["href"] = proxy_url

        # Inject a script to set the proxy's URL as a JavaScript variable that runs
        # after everything else
        script_tag = soup.new_tag("script")
        script_tag.string = f"window.CONFIG.domainBaseUrl = '{proxy_url}';"
        soup.body.append(script_tag)

        # Logging the response

        logging.info(f"Modified and returning HTML content for {path}")

        return Response(str(soup), resp.status_code, headers)

    # Logging the response
    logging.info(f"Forwarding non-HTML content for {path}")

    return Response(resp.content, resp.status_code, headers)


if __name__ == "__main__":
    app.run(debug=True)
