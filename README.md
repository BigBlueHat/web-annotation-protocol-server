# Web Annotation Protocol Server

This very basic [wptserve]()-based server supports the core features of the
[Web Annotation Protocol]() specification (no more, no less).

## Usage

```
$ pip install -r requirements.txt
$ python index.py
```

Visit `http://localhost:8080/`.

## Caution

This is a world-write-able server. There's zero security. It writes to disk. Proceed with appropriate caution.

## License

MIT
