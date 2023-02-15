import pickle as pk

from networkit import Graph, components, community, setNumberOfThreads, Partition
from numpy import argpartition, argsort, asarray, where, nonzero
from sklearn.neighbors import NearestNeighbors
from scipy import spatial

from . import strategy_loader
from . import strategy_norm
from .logger import logger
from .nfm import get_nfm_embeddings


class SINr(object):
    """Object that can be used to extract word or graph embeddings using the SINr approach.
    This object cannot then be used to inspect the resulting vectors. Instead, using the ModelBuilder class, a SINrVectors object should be created that will allow to use the resulting vectors.
    
    ...


    Attributes
    ----------
    Attributes should not be read
    """

    @classmethod
    def load_from_cooc_pkl(cls, cooc_matrix_path, norm=None, n_jobs=1):
        """Build a sinr object from a co-occurrence matrix stored as a pickle : useful to deal with textual data.
        Co-occurrence matrices should for instance be generated using sinr.text.cooccurrence

        :param cooc_matrix_path: Path to the cooccurrence matrix generated using sinr.text.cooccurrence : the file should be a pickle
        :type cooc_matrix_path: string
        :param norm: If the graph weights be normalized (for example using PMI). The default is None.
        :type norm: strategy_norm, optional
        :param n_jobs: Number of jobs that should be used The default is 1.
        :type n_jobs: int, optional

        
        """
        logger.info("Building Graph.")

        word_to_idx, matrix = strategy_loader.load_pkl_text(cooc_matrix_path)
        graph = get_graph_from_matrix(matrix)
        graph = strategy_norm.apply_norm(graph, norm)
        out_of_LgCC = get_lgcc(graph)
        logger.info("Finished building graph.")
        return cls(graph, out_of_LgCC, word_to_idx)

    @classmethod
    def load_from_adjacency_matrix(cls, matrix_object, norm=None, n_jobs=1):
        """Build a sinr object from an adjacency matrix as a sparse one (csr)

        :param matrix_object: Matrix describing the graph.
        :type matrix_object: csr_matrix
        :param norm: If the graph weights be normalized (for example using PMI). The default is None.
        :type norm: strategy_norm, optional
        :param n_jobs: Number of jobs that should be used The default is 1.
        :type n_jobs: int, optional

        
        """
        logger.info("Building Graph.")
        word_to_idx, matrix = strategy_loader.load_adj_mat(matrix_object)
        graph = get_graph_from_matrix(matrix)
        graph = strategy_norm.apply_norm(graph, norm)
        out_of_LgCC = get_lgcc(graph)
        logger.info("Finished building graph.")
        return cls(graph, out_of_LgCC, word_to_idx)

    @classmethod
    def load_from_graph(cls, graph, norm=None, n_jobs=1):
        """Build a sinr object from a networkit graph object

        :param graph: Networkit graph object.
        :type graph: networkit
        :param norm: If the graph weights be normalized (for example using PMI). The default is None.
        :type norm: strategy_norm, optional
        :param n_jobs: Number of jobs that should be used The default is 1.
        :type n_jobs: int, optional

        
        """
        word_to_idx = dict()
        idx = 0
        for u in graph.iterNodes():
            word_to_idx[u] = idx
            idx += 1
        graph = strategy_norm.apply_norm(graph, norm)
        out_of_LgCC = get_lgcc(graph)
        logger.info("Finished building graph.")
        return cls(graph, out_of_LgCC, word_to_idx)

    def run(self, algo=None):
        """Runs the training of the embedding, i.e. community detection + vectors extraction

        :param algo: Community detection algorithm. The default, None allorws to run a Louvain algorithm
        :type algo: networkit.algo.community, optional

        
        """
        if algo is None:
            algo = community.PLM(self.cooc_graph, refine=False, gamma=1, turbo=True, recurse=False)
        self.communities = self.detect_communities(self.cooc_graph, algo=algo)
        self.extract_embeddings(communities=self.communities)

    def detect_communities(self, gamma=100, algo=None, inspect=True):
        """Runs community detection on the graph

        :param gamma: For Louvain algorithm which is the default algorithm (ignore this parameter if param algo is used), allows to control the size of the communities. The greater it is, the smaller the communities. The default is 100.
        :type gamma: int, optional
        :param algo: Community detection algorithm. The default, None allorws to run a Louvain algorithm
        :type algo: networkit.algo.community, optional
        :param inspect: Whether or not one wants to get insight about the communities extracted. The default is True.
        :type inspect: boolean, optional

        
        """
        logger.info("Detecting communities.")
        print(f"Gamma for louvain : {gamma}")
        if algo is None:
            algo = community.PLM(self.cooc_graph, refine=False, gamma=gamma, turbo=True, recurse=False)
        communities = community.detectCommunities(self.cooc_graph, algo=algo, inspect=inspect)
        communities.compact(useTurbo=True)  # Consecutive communities from 0 to number of communities - 1
        self.communities = communities
        logger.info("Finished detecting communities.")
        return communities

    def size_of_voc(self):
        """ """
        return len(self.idx_to_wrd)

    def transfert_communities_labels(self, community_labels, refine=False):
        """Transfer communities computed on one graph to another, used mainly with co-occurence graphs.

        :param community_labels: a list of communities described by sets of labels describing the nodes
        :param refine:  (Default value = False)
        :returns: Initializes a partition where nodes are all singletons. Then, when communities in parameters contain labels
        that are in the graph at hand, these communities are transferred.

        """
        self.communities = Partition(self.size_of_voc())
        self.communities.allToSingletons()
        for com in community_labels:
            new_com = []
            # Check if labels in communities passed as parameters are in the graph at hand, if so -> transfer the community
            for word in com:
                if word in self.wrd_to_idx:
                    new_com.append(self.wrd_to_idx[word])
            # Transferring the community to the graph at hand
            if len(new_com) > 1:
                subset_id = self.communities.subsetOf(new_com[0])
                for idx in range(1, len(new_com)):
                    self.communities.moveToSubset(subset_id, new_com[idx])
        # Compating the community ids
        self.communities.compact()
        if refine:
            self._refine_transfered_communities()

    """def _refine_transfered_communities(self):"""


    def extract_embeddings(self, communities=None):
        """

        :param communities: Community structures (Default value = None)
        :type communities: networkit partition

        
        """
        logger.info("Extracting embeddings.")

        if communities is not None:
            self.communities = communities

        logger.info("Applying NFM.")
        np, nr, nfm = get_nfm_embeddings(self.cooc_graph, self.communities.getVector(), self.n_jobs)
        self.np = np
        self.nr = nr
        self.nfm = nfm
        logger.info("NFM successfully applied.")
        logger.info("Finished extracting embeddings.")

    def __init__(self, graph, lgcc, wrd_to_idx, n_jobs=1):
        """
        Should not be used ! Some factory methods below starting with "load_" should be used instead.

        Parameters
        ----------
        graph : networkit graph
        lgcc : networkit graph
            the largest connected component of graph
        wrd_to_idx : dict
            A matching between a vocabulary and ids. Useful for text. Otherwise, the vocabulary and the ids are the same
        n_jobs : int, optional
            Number of jobs that should be runned. The default is 1

        Returns
        -------
        None.

        """
        self.nfm = None
        self.nr = None
        self.np = None
        self.communities = None
        self.n_jobs = n_jobs
        setNumberOfThreads(n_jobs)
        self.wrd_to_idx = wrd_to_idx
        self.idx_to_wrd = _flip_keys_values(self.wrd_to_idx)
        self.cooc_graph = graph
        self.out_of_LgCC = lgcc

        self.wd_before, self.wd_after = None, None

    def get_out_of_LgCC_coms(self, communities):
        """Get communities that are not in the Largest Connected Component (LgCC).

        :param communities: Partition object of the communities as obtained by calling a Networkit community detection algorithm
        :type communities: Partition
        :returns: Indices of the comunnities outside the LgCC
        :rtype: list[int]

        """
        set_out_of_LgCC = set(self.out_of_LgCC)
        out_of_LgCC_coms = []
        for com in communities.getSubsetIds():
            if set(communities.getMembers()) & set_out_of_LgCC != {}:
                out_of_LgCC_coms.append(com)
        return out_of_LgCC_coms

    def get_cooc_graph(self):
        """ """
        return self.cooc_graph

    def get_nr(self):
        """ """
        if self.nr is None:
            raise NoEmbeddingExtractedException
        else:
            return self.nr

    def get_np(self):
        """ """
        if self.np is None:
            raise NoEmbeddingExtractedException
        else:
            return self.np

    def get_nfm(self):
        """ """
        if self.nfm is None:
            raise NoEmbeddingExtractedException
        else:
            return self.nfm

    def get_vocabulary(self):
        """ """
        return list(self.idx_to_wrd.values())

    def get_wrd_to_id(self):
        """ """
        return self.wrd_to_idx

    def get_communities(self):
        """ """
        if self.communities is None:
            raise NoCommunityDetectedException
        else:
            return self.communities


def _flip_keys_values(dictionary):
    """

    :param dictionary: 

    """
    return dict((v, k) for k, v in dictionary.items())


def get_lgcc(graph):
    """

    :param graph: 
    :type graph: networkit graph

    
    """
    out_of_LgCC = set(graph.iterNodes()) - set(components.ConnectedComponents.extractLargestConnectedComponent(
        graph).iterNodes())  # Extract out of largest connected component vocabulary
    return out_of_LgCC


def get_graph_from_matrix(matrix):
    """

    :param matrix: A sparse matrix describing a graph
    :type matrix: coo_matrix

    
    """
    graph = Graph(weighted=True)
    rows, cols = matrix.row, matrix.col
    weights = matrix.data
    for row, col, weight in zip(rows, cols, weights):
        graph.addEdge(u=row, v=col, w=weight, addMissing=True)
    return graph


class NoCommunityDetectedException(Exception):
    """ """
    pass


class NoEmbeddingExtractedException(Exception):
    """ """
    pass


class ModelBuilder:
    """Object that should be used after the training of word or graph embeddings using the SINr object.
    The ModelBuilder will make use of the SINr object to build a SINrVectors object that will allow to use the resulting vectors efficiently.
    ...


    Attributes
    ----------
    Attributes should not be read
    """

    def __init__(self, sinr, name, n_jobs=1, n_neighbors=31):
        """
        Creating a ModelBuilder object to build a SINrVectors one

        Parameters
        ----------
        sinr : SINr
            A SINr object with extracted vectors
        name : string
            Name of the model
        n_jobs : TYPE, optional
            DESCRIPTION. The default is 1.
        n_neighbors : int, optional
            Number of neighbors to use for similarity. The default is 31.

        Returns
        -------
        None.

        """
        self.sinr = sinr
        self.model = SINrVectors(name, n_jobs, n_neighbors)

    def with_embeddings_nr(self, threshold=0):
        """Adding Node Recall vectors to the SINrVectors object

        :param threshold:  (Default value = 0)

        """
        if threshold == 0:
            self.model.set_vectors(self.sinr.get_nr())
        else:
            coo = self.sinr.get_nr().tocoo()
            for idx, val in enumerate(coo.data):
                if val < threshold:
                    coo.data[idx] = 0
            coo.eliminate_zeros()
            self.model.set_vectors(coo.tocsr())
        return self

    def with_embeddings_nfm(self):
        """Adding NFM (Node Recall + Node Predominance) vectors to the SINrVectors object"""
        self.model.set_vectors(self.sinr.get_nfm())
        return self

    def with_np(self):
        """Storing Node predominance values in order to label dimensions for instance"""
        self.model.set_np(self.sinr.get_np())
        return self

    def with_vocabulary(self):
        """To deal with word vectors or graph when nodes have labels"""
        self.model.set_vocabulary(self.sinr.get_vocabulary())
        return self

    def with_communities(self):
        """To keep the interpretability of the model using the communities"""
        self.model.set_communities(self.sinr.get_communities())
        return self

    def with_graph(self):
        """To keep the underlying graph ; useful to get co-occ statistics, degree of nodes or to label communities with central nodes"""
        self.model.set_graph(self.sinr.get_cooc_graph())
        return self

    def with_all(self):
        """ """
        return self.with_embeddings_nr().with_vocabulary().with_communities().with_graph().with_np()

    def build(self):
        """To get the SINrVectors object"""
        return self.model
    
class OnlyGraphModelBuilder(ModelBuilder):
    """Object that should be used after training word or graph embeddings using the SINr object to get interpretable vectors.
    The OnlyGraphModelBuilder will make use of the SINr object to build a SINrVectors object that will allow to use the resulting vectors efficiently.
    No need to use parent methods starting by "with", those are included in the "build" function.
    Just provide the name of the model and build it.


    """
    def build(self):
        """ """
        self.with_np()
        return self.model

class InterpretableWordsModelBuilder(ModelBuilder):
    """Object that should be used after training word or graph embeddings using the SINr object to get interpretable word vectors.
    The InterpretableWordsModelBuilder will make use of the SINr object to build a SINrVectors object that will allow to use the resulting vectors efficiently.
    No need to use parent methods starting by "with", those are included in the "build" function.
    Juste provide the name of the model and build it.


    """

    def build(self):
        """ """
        self.with_embeddings_nr().with_vocabulary().with_communities()
        return self.model


class ThresholdedModelBuilder(ModelBuilder):
    """Object that should be used after the training of word or graph embeddings using the SINr object to get interpretable word vectors.
    The ThresholdedModelBuilder will make use of the SINr object to build a SINrVectors object that will allow to use the resulting vectors efficiently.
    Values in the vectors that are lower than the threshold will be discarded. Vectors are then sparser and more interpretable.
    No need to use parent methods starting by "with", those are included in the "build" function.
    Juste provide the name of the model and build it.


    """

    def build(self, threshold=0.01):
        """

        :param threshold:  (Default value = 0.01)

        """
        self.with_embeddings_nr(threshold=threshold).with_vocabulary().with_communities()
        return self.model


class NoInterpretabilityException(Exception):
    """ """
    "Raised when the communities were not included in the model that was built. It is thus not interpretable anymore."
    pass


class NoVocabularyException(Exception):
    """ """
    "Raised when no vocabulary was included in the model that was built. One cannot play with words."
    pass


class InterpretableDimension:
    """ """
    def __init__(self, idx, type):
        self.idx = idx
        self.type = type
        self.value = None
        self.interpreters = []

    def add_interpreter(self, obj, value):
        """

        :param obj: 
        :param value: 

        """
        self.interpreters.append((round(value, 2), obj))

    def get_idx(self):
        """ """
        return self.get_idx()

    def get_value(self):
        """ """
        return self.value

    def get_interpreters(self):
        """ """
        return self.interpreters

    def get_interpreter(self, id):
        """

        :param id: 

        """
        return self.interpreters[id]

    def sort(self, on_value=True):
        """

        :param on_value:  (Default value = True)

        """
        if on_value:
            self.interpreters.sort(key=lambda x: x[0], reverse=True)
        else:
            self.interpreters.sort(key=lambda x: x[1], reverse=True)

    def topk(self, topk):
        """

        :param topk: 

        """
        topk = min(topk, len(self.interpreters))
        self.interpreters = self.interpreters[:topk]

    def with_value(self, value):
        """

        :param value: 

        """
        self.value = value
        return self

    def get_dict(self):
        """ """
        result = {"dimension": self.idx, "value": self.value,
                  self.type: self.interpreters} if self.value is not None else {"dimension": self.idx,
                                                                                self.type: self.interpreters}
        return result

    def __repr__(self):
        return str(self.get_dict())


class SINrVectors(object):
    """After training word or graph embeddings using SINr object, use the ModelBuilder object to build SINrVectors.
    SINrVectors is the object to manipulate the model, explore the embedding space and its interpretability


    """
    labels: bool

    def __init__(self, name, n_jobs=1, n_neighbors=20):
        """
        Initializing SINr vectors objets
        @param name: name of the model, useful to save it
        @param n_jobs: number of jobs to use (k-nearest neighbors to obtain most similar words or nodes)
        @param n_neighbors: number of neighbors to consider when querying the most similar words or nodes
        """
        self.G = None
        self.communities_sets = None
        self.community_membership = None
        self.np = None
        self.neighbors = None
        self.vocab = None
        self.vectors = None
        self.name = name
        self.n_jobs = n_jobs
        self.n_neighbors = n_neighbors
        self.labels = False

    def get_communities_as_labels_sets(self):
        """Get partition of communities as a list of sets each containing the label associates to the node in the community.


        :returns: List of communities each represented by a set of labels associated to the node in each subset

        :rtype: list[set[str]]
        :raises NoInterpretabilityException: SINrVector was not exported with interpretable dimensions

        """
        if self.communities_sets is None:
            raise NoInterpretabilityException
        labels_sets = []
        for com in self.communities_sets:
            labels = set()
            for u in com:
                labels.add(self.vocab[u])
            labels_sets.append(labels)
        return labels_sets

    def set_n_jobs(self, n_jobs):
        """Set the number of jobs.

        :param n_jobs: number of jobs

        """
        self.n_jobs = n_jobs

    def set_graph(self, G):
        """Set the graph property.

        :param G: A networkit graph
        :type G: networkit.Graph

        """
        self.G = G

    def get_nnz(self):
        """Get the count of non-zero values in the embedding matrix.


        :returns: number of non zero values

        """
        return self.vectors.getnnz()
    
    def get_nz_dims(self, obj) :
        """

        :param obj: 
        :returns: set of indexes of non zero dimensions

        """
        index = self._get_index(obj)
        vector = self._get_vector(index, row=True)
        return set(list(nonzero(vector)[0]))
    
    def get_value_dim_per_word(self, obj, dim_index):
        """

        :param obj: 
        :param dim_index: 
        :returns: the NR value for a given vector on a given dimension

        """
        index = self._get_index(obj)
        vector = self._get_vector(index, row=True)
        dict_in_dim = InterpretableDimension(dim_index,"descriptors").with_value(vector[dim_index]).get_dict()
        value = dict_in_dim["value"]
        return value
     
    def get_nnv(self):
        """Get the number of null-vetors in the embedding matrix.


        :returns: number of null vectors

        """
        sum = self.vectors.sum(axis=1)
        nulls = where(sum == 0)[0]
        return len(nulls)

    def pct_nnz(self):
        """Get the percentage of non-zero values in the embedding matrix


        :returns: percentage of non-zero values in the embedding matrix

        """
        nnz = self.get_nnz()
        return (nnz * 100) / (self.vectors.shape[0] * self.vectors.shape[1])

    def set_vocabulary(self, voc):
        """Set the vocabulary for word-co-occurrence graphs.

        :param voc: set the vocabulary when dealing with words or nodes with labels. label parameter is set to True.
        By default, labels from the vocab will be used.

        """
        self.vocab = voc
        # self.wrd_to_id = wrd_to_id
        self.labels = True

    def set_vectors(self, embeddings):
        """Set the embedding vectors and initialize nearest neighbors.

        :param embeddings: initialize the vectors and build the nearest neighbors data structure using sklearn

        """
        self.vectors = embeddings
        self.neighbors = NearestNeighbors(n_neighbors=self.n_neighbors, metric='cosine', n_jobs=self.n_jobs).fit(
            self.vectors)

    def set_np(self, np):
        """Set the embedding matrix.

        :param np: A sparse matrix of the embeddings
        :type np: Scipy.sparse.csr_matrix

        """
        self.np = np

    def set_communities(self, com):
        """

        :param com: 

        """
        self.community_membership = com.getVector()
        nb_coms = max(self.community_membership)
        self.communities_sets = []
        for i in range(nb_coms + 1):
            self.communities_sets.append(set())
        for idx, com in enumerate(self.community_membership):
            self.communities_sets[com].add(idx)

    def get_community_membership(self, obj):
        """Get the community index of a node or label.

        :param obj: an integer of the node or of its label
        :returns: the community of a specific object

        """
        if self.communities_sets is None:
            raise NoInterpretabilityException
        index = self._get_index(obj)
        return self.community_membership[index]

    def get_community_sets(self, idx):
        """Get the indices of the nodes in for a specific community.

        :param obj: an integer index of a community
        :param idx: 
        :returns: the set of ids of nodes belonging to this community

        """
        if self.communities_sets is None:
            raise NoInterpretabilityException
        return self.communities_sets[idx]

    def _get_index(self, obj):
        """Returns the index for a label or an index.

        :param obj: The object fro which the index should be fetched
        :returns: The index of the object

        """
        if type(obj) is int:
            return obj
        index = self.vocab.index(obj) if self.labels else obj
        return index

    def most_similar(self, obj):
        """Get the most similar objects of the one passed as a parameter using the cosine of their vectors

        :param obj: The object for which to fetch the nearest neighbors. Can be int of str.
        :type obj: integer or string

        
        """
        index = self._get_index(obj)

        distances, neighbor_idx = self.neighbors.kneighbors(self.vectors[index, :], return_distance=True)
        # print(similarities, neighbor_idx)
        return {"object ": obj,
                "neighbors ": [(self.vocab[nbr] if self.labels else nbr, round(1 - dist, 2)) for dist, nbr in
                               list(zip(distances.flatten(), neighbor_idx.flatten()))[1::]]}

    def _get_vector(self, idx, row=True):
        """Returns a list from the csr matrix

        :param idx: id of the vector requested
        :param row: if the vector should be a row or a column of the csr matrix of embeddings (Default value = True)
        :returns: the vector

        """
        vector = asarray(self.vectors.getrow(idx).todense()).flatten() if row else asarray(
            self.vectors.getcol(idx).todense()).flatten()
        return vector
    
    def cosine_sim(self, obj1, obj2):
        """
        return cosine similarity between specified item of the model
        """
        id1 = self._get_index(obj1)
        id2 = self._get_index(obj2)
        vec1 = self._get_vector(id1)
        vec2 = self._get_vector(id2)
        cos_dist = spatial.distance.cosine(vec1, vec2)
        return 1-cos_dist
        
    def _get_topk(self, idx, topk=5, row=True):
        """Returns indices of the topk values in the vector of id idx

        :param idx: idx of the vector in which the topk values are searched
        :param topk: number of values to get (Default value = 5)
        :param row: if the vector is a row or a column (Default value = True)
        :returns: the indices of the topk values in the vector

        """
        vector = self._get_vector(idx, row)
        topk = -topk
        ind = argpartition(vector, topk)[topk:]
        ind = ind[argsort(vector[ind])[::-1]]
        return ind
    
    def get_topk_dims(self, obj, topk=5):
        """

        :param obj: 
        :param topk:  (Default value = 5)

        """
        index = self._get_index(obj)
        return self._get_topk(index, topk, True)

    def get_value_obj_dim(self, obj, dim):
        """

        :param obj: 
        :param dim: 

        """
        index = self._get_index(obj)
        vector = self._get_vector(index)
        return vector[dim]

    # Using communities to describe dimensions
    def get_dimension_descriptors(self, obj, topk=-1):
        """Returns the objects that constitute the dimension of obj, i.e. the members of the community of obj

        :param obj: id, word
        :param topk:  (Default value = -1)
        :returns: a set of object, the community of obj

        """
        if self.communities_sets is None:
            raise NoInterpretabilityException
        index = self._get_index(obj)
        return self.get_dimension_descriptors_idx(self.community_membership[index], topk)

    def get_dimension_descriptors_idx(self, index, topk=-1):
        """Returns the objects that constitute the dimension of obj, i.e. the members of the community of obj

        :param topk: 1 returns all the members of the community, a positive int returns juste the topk members with
        highest nr values on the community (Default value = -1)
        :param idx: id of dimension
        :param index: 
        :returns: a set of object, the community of obj

        """
        if self.communities_sets is None:
            raise NoInterpretabilityException
        vector = self._get_vector(index, row=False)
        in_dim = InterpretableDimension(index, "descriptors")
        for member in self.get_community_sets(index):
            in_dim.add_interpreter(self.vocab[member], vector[member]) if self.labels else in_dim.add_interpreter(
                member, vector[member])
        in_dim.sort(on_value=True)
        if topk >= 1:
            in_dim.topk(topk)
        return in_dim
        # community_nr = [(round(vector[member], 2), self.vocab[member]) for member in self.get_community_sets(index)]
        # community_nr.sort(key=lambda x: x[0], reverse=True)
        # if topk < 1:
        #     return community_nr
        # else:
        #     topk = min(topk, len(community_nr))
        #     return community_nr[:topk]

    def get_obj_descriptors(self, obj, topk_dim=5, topk_val=-1):
        """Returns the descriptors of the dimensions of obj.

        :param topk_dim: int, topk dimensions to consider to describe obj (Default value = 5)
        :param obj: an id or a word/label
        :param topk_val: 1 returns all the members of the community, a positive int returns juste the topk members with
        highest nr values on the community (Default value = -1)
        :returns: the dimensions (and the objects that constitute these dimensions) that matter to describe obj

        """
        if self.communities_sets is None:
            raise NoInterpretabilityException
        index = self._get_index(obj)
        highest_dims = self._get_topk(index, topk_dim, row=True)
        vector = self._get_vector(index, row=True)
        highest_dims = [self.get_dimension_descriptors_idx(idx, topk_val).with_value(vector[idx]).get_dict() for idx in
                        highest_dims]
        return highest_dims

    # Using top words to describe dimensions
    def get_dimension_stereotypes(self, obj, topk=5):
        """Get the words with the highest values on dimension obj.

        :param obj: id of a dimension, or label of a word (then turned into the id of its community)
        :param topk: topk value to consider on the dimension (Default value = 5)
        :returns: the topk words that describe this dimension (highest values)

        """
        index = self._get_index(obj)
        return self.get_dimension_stereotypes_idx(self.get_community_membership(index), topk)

    def get_dimension_stereotypes_idx(self, idx, topk=5):
        """Get the indices of the words with the highest values on dimension obj.

        :param obj: id of a dimension, or label of a word (then turned into the id of its community)
        :param topk: topk value to consider on the dimension (Default value = 5)
        :param idx: 
        :returns: the topk words that describe this dimension (highest values)

        """
        highest_idxes = self._get_topk(idx, topk, row=False)
        vector = self._get_vector(idx, row=False)
        in_dim = InterpretableDimension(idx, "stereotypes")
        for idx in highest_idxes:
            in_dim.add_interpreter(self.vocab[idx], vector[idx]) if self.labels else in_dim.add_interpreter(idx,
                                                                                                            vector[idx])
        return in_dim

    def get_obj_stereotypes(self, obj, topk_dim=5, topk_val=3):
        """Get the top dimensions for a word.

        :param obj: the word to consider
        :param topk_dim: topk dimension to consider (Default value = 5)
        :param topk_val: topk values to describe each dimension (Default value = 3)
        :returns: the most useful dimensions to describe a word and for each dimension,
        the topk words that describe this dimension (highest values)

        """
        # get index of the word considered
        index = self._get_index(obj)
        # get the topk dimensions for this word
        highest_dims = self._get_topk(index, topk_dim, row=True)
        vector = self._get_vector(index, row=True)
        highest_dims = [self.get_dimension_stereotypes_idx(idx, topk_val).with_value(vector[idx]).get_dict() for idx in
                        highest_dims]
        return highest_dims

    def get_obj_stereotypes_and_descriptors(self, obj, topk_dim=5, topk_val=3):
        """Get the stereotypes and descriptors for obj.

        :param obj: 
        :param topk_dim:  (Default value = 5)
        :param topk_val:  (Default value = 3)
        :returns: both stereotypes and descriptors

        """
        sters = self.get_obj_stereotypes(obj, topk_dim, topk_val)
        descs = self.get_obj_descriptors(obj, topk_dim, topk_val)
        for ster, desc in zip(sters, descs):
            ster["descriptors"] = desc["descriptors"]
        return sters

    def get_number_of_dimensions(self):
        """Get the number of dimensions of model.


        :returns: Number of dimensions of the model.

        :rtype: int

        """
        return len(self.communities_sets)

    def load(self):
        """Load a SINrVectors model."""
        f = open(self.name + ".pk", 'rb')
        tmp_dict = pk.load(f)
        f.close()
        self.__dict__.update(tmp_dict)

    def save(self):
        """Save a SINrVectors model."""
        f = open(self.name + ".pk", 'wb')
        pk.dump(self.__dict__, f, 2)
        f.close()

#    def save(self, output_path):
#        with open(output_path, 'wb+') as file:
#            pk.dump((self.vocab, self.vectors), file)

#    def load(model_path):
#        with open(model_path, 'rb') as file:
#            vocab, vectors = pk.load(file)
#        return Model(vocab, vectors)
    def get_my_vector(self, obj, row=True):
        """Get the column or the row obj.

        :param obj: Index of the row/column to return.
        :type obj: int
        :param row: Return a row if True else a column. Defaults to True.
        :type row: bool
        :returns: A row/column.
        :rtype: np.ndarray

        """
        index = self._get_index(obj)
        vector = asarray(self.vectors.getrow(index).todense()).flatten() if row else asarray(
            self.vectors.getcol(index).todense()).flatten()
        return vector
    
    def light_model_save(self):
        """Save a minimal version of the model that is readable as a dict for evaluation on word-embeddings-benchmark
        https://github.com/kudkudak/word-embeddings-benchmarks


        """
        data={}
        for item in self.vocab :
            data[item]=self.get_my_vector(item)
        f = open(self.name + "_light.pk", 'wb')
        pk.dump(data,f)
        f.close()