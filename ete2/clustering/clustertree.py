import sys

from numpy import nan as NaN # Missing values in array are saved as
			     # NaN values

import clusterdist as DistFunction
from ete2 import TreeNode, ArrayTable

__all__ = ["ClusterNode", "ClusterTree", "DistFunction"]

class ClusterNode(TreeNode):
    """ Creates a new Cluster Tree object, which is a collection
    of ClusterNode instances connected in a hierarchical way, and
    representing a clustering result. 

    a newick file or string can be passed as the first argument. An
    ArrayTable file or instance can be passed as a second argument.
    
    Examples:
      t1 = Tree() # creates an empty tree
      t2 = Tree( '(A:1,(B:1,(C:1,D:1):0.5):0.5);' )  
      t3 = Tree( '/home/user/myNewickFile.txt' )
    """

    def _set_forbidden(self, value):
        raise ValueError, "This attribute can not be manually set."

    def _get_intra(self):
        if self._silhouette == None:
            self.get_silhouette()
        return self._intracluster_dist
    
    def _get_inter(self):
        if self._silhouette == None:
            self.get_silhouette()
        return self._intercluster_dist

    def _get_silh(self):
        if self._silhouette == None:
            self.get_silhouette()
        return self._silhouette

    def _get_prof(self):
        if self._profile is None:
            self._calculate_avg_profile()
        return self._profile

    def _get_std(self):
        if self._std_profile is None:
            self._calculate_avg_profile()
        return self._std_profile

    def _set_profile(self, value):
        self._profile = value
    
    intracluster_dist = property(fget=_get_intra, fset=_set_forbidden)
    intercluster_dist = property(fget=_get_inter, fset=_set_forbidden)
    silhouette = property(fget=_get_silh, fset=_set_forbidden)
    profile = property(fget=_get_prof, fset=_set_profile)
    deviation = property(fget=_get_std, fset=_set_forbidden)
    
    def __init__(self, newick = None, text_array = None, \
                 fdist=DistFunction.spearman_dist):
	# Initialize basic tree features and loads the newick (if any)
        TreeNode.__init__(self, newick)
        self._fdist = None
        self._silhouette = None
	self._intercluster_dist = None
	self._intracluster_dist = None
	self._profile = None
	self._std_profile = None

	# Cluster especific features
        self.features.add("intercluster_dist")
        self.features.add("intracluster_dist")
        self.features.add("silhouette")
        self.features.add("profile")
        self.features.add("deviation")

	# Initialize tree with array data
	if text_array:
	    self.link_to_arraytable(text_array)

        if newick:
            self.set_distance_function(fdist)

    def set_distance_function(self, fn):
        for n in self.traverse():
            n._fdist = fn

    def link_to_arraytable(self, arraytbl):
	""" Allows to link a given arraytable object to the tree
	structure under this node. Row names in the arraytable object
	are expected to match leaf names. 

	Returns a list of nodes for with profiles could not been found
	in arraytable.
	
	"""

	# Initialize tree with array data

	if type(arraytbl) == ArrayTable:
	    array = arraytbl
	else:
	    array = ArrayTable(arraytbl)

	missing_leaves = []
	for n in self.traverse():
	    n.arraytable = array
	    if n.is_leaf() and n.name in array.rowNames:
		n._profile = array.get_row_vector(n.name)
	    elif n.is_leaf():
		n._profile = [NaN]*len(array.colNames) 
		missing_leaves.append(n)


	if len(missing_leaves)>0:
	    print >>sys.stderr, \
		"""[%d] leaf names could not be mapped to the matrix rows.""" %\
		len(missing_leaves)

	self.arraytable = array

    def iter_leaf_profiles(self):
	""" Returns an iterator over all the profiles associated to
	the leaves under this node."""
	for l in self.iter_leaves():
	    yield l.get_profile()[0]

    def get_leaf_profiles(self):
	""" Returns the list of all the profiles associated to the
	leaves under this node."""
	return [l.get_profile()[0] for l in self.iter_leaves()]

    def get_silhouette(self, fdist=None):
        """ Calculates the node's silhouette value by using a given
        distance function. By default, euclidean distance is used. It
        also calculates the deviation profile, mean profile, and
        inter/intra-cluster distances. 

	It sets the following features into the analyzed node:
	   - node.intracluster_d
	   - node.intercluster_d
	   - node.silhouete 

	intracluster distances a(i) are calculated as the centroid
	distance.

	intercluster distances b(i) are calculated as the Average to
	Centroid Linkage.

	** Rousseeuw, P.J. (1987) Silhouettes: A graphical aid to the
	interpretation and validation of cluster analysis.
	J. Comput. Appl. Math., 20, 53-65.

        """

        if fdist is None:
            fdist = self._fdist
        
        sisters = self.get_sisters()
        
        # Calculates average vectors
        if self._profile is None:
            self._calculate_avg_profile()
            
        for st in sisters:
            if st._profile is None:
                st._calculate_avg_profile()
                
        # Calculates silhouette
	silhouette = []
        intra_dist = []
        inter_dist = []
        for st in sisters:
            if st._profile is None:
		continue

            for i in self.iter_leaves():
                # Skip nodes with nodes without profile
                if i._profile is not None:
		    # Centroid Diameter
		    a = fdist(i._profile, self._profile)*2
		    # Centroid Linkage
		    b = fdist(i._profile, st._profile) 
		    if (b-a) == 0.0:
			s = 0.0
		    else:
			s =  (b-a) / max(a,b)
		    intra_dist.append(a)
		    inter_dist.append(b)
		    silhouette.append(s)

        self._silhouette, std = DistFunction.safe_mean(silhouette)
        self._intracluster_dist, std = DistFunction.safe_mean(intra_dist)
        self._intercluster_dist, std = DistFunction.safe_mean(inter_dist)
        return self.silhouette, self.intracluster_dist, self.intercluster_dist

    def _calculate_avg_profile(self):
	""" This internal function updates the mean profile
	associated to an internal node. """

	if not self.is_leaf():
	    leaf_vectors = [n._profile for n in  self.get_leaves() \
				if n._profile is not None]
	    if len(leaf_vectors)>0:
		self._profile, self._std_profile = DistFunction.safe_mean_vector(leaf_vectors)
	    else:
		self._profile, self._std_profile = None, None
	    return self._profile, self._std_profile
	else: 
	    self._std_profile = [0.0]*len(self._profile)
	    return self._profile, [0.0]*len(self._profile)


# cosmetic alias
ClusterTree = ClusterNode
