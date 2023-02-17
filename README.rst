.. _Networkit: https://networkit.github.io


==============================
SINr
==============================

SINr is an open-source tool to efficiently compute graph and word embeddings.
Its aim is to provide sparse interpretable vectors from a graph structure.
The dimensions of the vector produced are related to the community structure
detected in the graph. By leveraging the relative connection of vertices to 
communities, SINr builds an interpretable space. SINr is focused on providing
tools to build and interpret the embeddings produced.

SINr is a Python module relying on `Networkit`_ 
for the graph structure and community detection. SINr also provides efficient
implementations to extract word co-occurrence graphs from large text corpora.
One of the strength of SINr is its ability to work with text and produce 
interpretable word embeddings that are competitive with similar approaches.
For more details on the performances of SINr on downstream evaluation tasks,
please refer to the :ref:`Publications` section.



Requirements
------------

- As SINr relies on libraries implemented using C/C++, a modern C++ compiler is required.
- OpenMP (required for `Networkit`_ and compiling `SINr`'s `Cython`)
- Python 3.9
- Pip
- Cython
- Conda (recommended)

Install
-------

SINr can be installed through `pip` or from source using `poetry` directives.

pip::
^^^^^^^
    #Activate conda environment
    conda activate sinr
    pip install sinr


from source::
^^^^^^^^^^^
    #Activate conda environment
    conda activate sinr
    git clone git@github.com:SINr-Embeddings/sinr.git
    cd sinr
    pip install poetry #poetry solves dependencies and installs SINr
    poetry install #Installs SINr based on the pyproject.toml file


Usage example
---------

To get started using SINr to build graph and word embeddings, have a look at the
`notebook <https://github.com/SINr-Embeddings/sinr/tree/main/notebooks>`_ 
directory.

Here is a minimum working example of SINr : ::

    import urllib
    import io
    import gzip
    import networkit as nk
    import sinr.graph_embeddings as ge


    url = "https://snap.stanford.edu/data/wiki-Vote.txt.gz"
    graph_file = "wikipedia-votes.txt"
    # Read a graph from SNAP
    sock = urllib.request.urlopen(url)  # open URL
    s = io.BytesIO(sock.read())  # read into BytesIO "file"
    sock.close()
    with gzip.open(s, "rt") as f_in:
        with open(graph_file, "wt") as f_out:
            f_out.writelines(f_in.readlines())
    # Initialize a networkit.Graph object from SNAP graph
    G = nk.readGraph(graph_file, nk.Format.SNAP)

    # Build a SINr model and extract embeddings
    model = ge.SINr.load_from_graph(G)
    model.run(algo=nk.community.PLM())
    embeddings = model.get_nr()
    print(embeddings)


Documentation
-------------

The documentation for SINr is `available online <https://sinr-embeddings.github.io/sinr/_build/html/index.html>`_.

Contributing
------------

Pull requests are welcome. For major changes, please open an issue first to disccus the changes to be made.


License
-------

Releaser under `CeCILL 2.1 <https://cecill.info/>`_

.. _Publications:

Publications
------------

SINr is currently maintained at the University of Le Mans. If you find SINr useful
for your own research, please cite the appropriate papers from the list below. 
Publications can also be found on `publications page in the documentation <https://sinr-embeddings.github.io/sinr/_build/html/publications.html>`_.

Initial SINr paper, 2021
------------------------

- Thibault Prouteau, Victor Connes, Nicolas Dugué, Anthony Perez, Jean-Charles Lamirel, et al.. SINr: Fast Computing of Sparse Interpretable Node Representations is not a Sin!. Advances in Intelligent Data Analysis XIX, 19th International Symposium on Intelligent Data Analysis, IDA 2021, Apr 2021, Porto, Portugal. pp.325-337, ⟨`10.1007/978-3-030-74251-5_26 <https://dx.doi.org/10.1007/978-3-030-74251-5_26>`_⟩. `⟨hal-03197434⟩ <https://hal.science/hal-03197434>`_

Interpretability of SINr embeddings, 2022
-----------------------------------------

- Thibault Prouteau, Nicolas Dugué, Nathalie Camelin, Sylvain Meignier. Are Embedding Spaces Interpretable? Results of an Intrusion Detection Evaluation on a Large French Corpus. LREC 2022, Jun 2022, Marseille, France. `⟨hal-03770444⟩ <https://hal.science/hal-03770444>`_