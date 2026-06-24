"""
LAYER: app (package root)
RESPONSIBILITY: Marks the Python package boundary for the FastAPI application
WHY IT EXISTS: Python requires __init__.py to treat a directory as a package,
               enabling absolute imports like `from app.config import Settings`
DEPENDS ON: Nothing (root package)
"""
# Package root for estimador-cag application
