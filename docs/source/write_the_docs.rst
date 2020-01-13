Write The Docs!
###############

**Ash** being a project built with a **Documentation Driven** approach means that a solid,
automated documentation procedure is a mandatory requirement.

The core components of our systems are:

   * Sphinx for the documentation generation
   * reStructuredText as the markup language
   * Google Style docstrings for in-code documentation
   * `vale`_ and `vale-styles`_
   * Automatic internal deployment via GitLab Pages CI/CD integration

This document goal is threefold:

   1. Explaining the Documentation Architecture, the steps taken to automate
      it and defending such choices
   2. Serve as a future reference for other projects
   3. Act as an example for the Guide format and a demo of Sphinx + reST superpowers
   4. Convince you of the need to always be on the lookout for errors even in a perfect
         system.


The Whys
********

Why Sphinx?
===========

Sphinx is the most used documentation framework for Python, developed for the Standard
library itself it's now adopted by all the most known third party libraries. What makes
Sphinx so great is the combination of extensibility via themes, extensions and what not,
coupled with a plethora of builtin functionalities that make writing decs a breeze.:

An example from Sphinx Site:

- Output formats: HTML (including Windows HTML Help), LaTeX (for printable PDF versions), ePub, Texinfo, manual pages, plain text
- Extensive cross-references: semantic markup and automatic links for functions, classes, citations, glossary terms and similar pieces of information
- Hierarchical structure: easy definition of a document tree, with automatic links to siblings, parents and children
- Automatic indices: general index as well as a language-specific module indices
- Code handling: automatic highlighting using the Pygments highlighter
- Extensions: automatic testing of code snippets, inclusion of docstrings from Python modules (API docs), and more
- Contributed extensions: more than 50 extensions contributed by users in a second repository; most of them installable from PyPI

Why reST?
=========

More than why reST, the real question is *Why not Markdown?*

While Markdown can be easier and slightly quicker to write, it does not offer the same
level of fine grained control, necessary for an effort as complex as technical writing,
without sacrificing portability.

*Eric Holscher* has an aptly named article: `Why You Shouldn’t Use “Markdown” for Documentation`_,
he is one of the greatest documentation advocate out there. Go and read his articles, they
are beautiful.

Why Google Style for Docstrings?
================================

Google Docstrings are to us the best way to organically combine code and documentation.
Leveraging Napoleon, a Sphinx extension offering automatic documentation support for
both Numpy and Google docstrings style, we can write easy to read docstrings and still
be able to use ``autodoc`` and ``autosummary`` directives.

Documentation Architecture
**************************

Tutorials, Guides, Complex Examples
===================================

Any form of documentation which is not generated from the codebase should go here.
Parent/Entry Point reStructuredText file, should be added in ``docs/src`` and then referenced
in ``index.rst``

API Reference
=============

API reference contains the full API documentation automatically generated from our
codebase. The only manual step required is adding the module you want to document to
the ``api.rst`` located inside ``docs/source``.

Automate all the docs!
----------------------

Classes, Functions, Exceptions: Annotate them normally, they do not require anything else.

Autosummary & submodules with imports: A painful story
------------------------------------------------------

Exposing Python objects to their parent module by importing them in its ``__init__.py``
file, breaks the ``autosummary`` directives when combining it with the automatic generation
of stub files. Currently there's no way of making ``autosummary`` aware of the imported
objects thus if you desire to document that API piece you need to find a workaround.

Example
_______

Suppose we have the following structure::

   keras/
      |---> __init__.py
      |
      |---> models.py

And that these two file contains respectively:

* __init__.py

.. code:: python

   from .models import Model

   __ALL__ = ["Model"]

* models.py

.. code:: python

   class Model:
      pass

Calling the ``autosummary`` directive (with the ``toctree`` option) on ``keras`` will not
generate stub files for ``keras.Model`` causing it to not show in the Table of Contents
of our API reference.

To circumvent this limitation it is ideal to insert some manual labour into the ``keras``
docstring.

* __init__.py

.. code:: python

   """
   Documentation example.

   .. rubric:: Classes

   .. autosummary:: Classes
      :toctree: _autosummary
      :nosignatures:

      keras.Model

   .. rubric:: Submodules

   .. autosummary:: keras.models
      :toctree: _autosummary
      :nosignatures:
      :template: autosummary/submodule.rst

      keras.models
   """
   from .models import Model

   __ALL__ = ["Model"]

This way ``autosummary`` will produce the proper API documentation. The same approach
applies also when exposing functions,exceptions, and modules.

.. note::
   used when annotating submodules.

Inheritance Diagrams
====================

Inheritance Diagrams are drawn using ``sphinx.ext.inheritance_diagram`` and ``sphinx.ext.graphviz``.

The ``autosummary`` template for classes has been modified in order to automatically
generate an inheritance diagram just below the title.

An ``Inheritances Diagrams`` page is manually created in order to showcase all the
diagrams in one single page. The page gives a quick overview of the relations between
the classes of each module.

Additional Materials
********************

* `Sphinx <http://www.sphinx-doc.org/en/master/index.html>`_
* `Google Pythony Style <https://google.github.io/styleguide/pyguide.html>`_
* `Google Developer Documentation Style Guide <https://developers.google.com/style/highlights>`_
* `Napoleon - Example Google Style Python Docstrings <https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html>`_
* `Read the Docs Sphinx Theme <https://sphinx-rtd-theme.readthedocs.io/en/stable/>`_
* `Write the Docs <https://www.writethedocs.org/>`_
* `reStructuredText Primer <http://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html#restructuredtext-primer>`_
* `vale <https://errata-ai.github.io/vale/>`_
* `Eric Holscher <http://www.ericholscher.com/#home>`_

.. Links
.. #####

.. _vale: https://github.com/errata-ai/vale/
.. _vale-styles: https://github.com/testthedocs/vale-styles
.. _Why You Shouldn’t Use “Markdown” for Documentation: https://www.ericholscher.com/blog/2016/mar/15/dont-use-markdown-for-technical-docs/#why-you-shouldn-t-use-markdown-for-documentation
