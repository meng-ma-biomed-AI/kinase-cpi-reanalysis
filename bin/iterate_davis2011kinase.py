import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import rankdata
import sys

from gaussian_process import SparseGPRegressor
from hybrid import HybridMLPEnsembleGP
from process_davis2011kinase import process, visualize_heatmap
from train_davis2011kinase import train
from utils import tprint

def acquisition_rank(y_pred, var_pred, beta=1.):
    beta = 100. ** (beta - 1.)
    return rankdata(y_pred) + ((1. / beta) * rankdata(-var_pred))

def acquisition_ucb(y_pred, var_pred, beta=1):
    return y_pred - (beta * var_pred)

def debug_selection(regress_type='gp'):#, **kwargs):
    y_obs_pred = np.loadtxt('target/ytrue_unknown_regressors{}.txt'
                            .format(regress_type))
    y_unk_pred = np.loadtxt('target/ypred_unknown_regressors{}.txt'
                            .format(regress_type))
    var_unk_pred = np.loadtxt('target/variance_unknown_regressors{}.txt'
                              .format(regress_type))

    for beta in [ 'rank', 100000, 500000, 1000000, ]:
        if beta == 'rank':
            acquisition = acquisition_rank(y_unk_pred, var_unk_pred)
        else:
            acquisition = acquisition_ucb(y_unk_pred, var_unk_pred, beta=beta)
        plt.figure()
        plt.scatter(y_unk_pred, var_unk_pred, alpha=0.3, c=acquisition)
        plt.viridis()
        plt.title(regress_type.title())
        plt.xlabel('Predicted score')
        plt.ylabel('Variance')
        plt.savefig('figures/acquisition_unknown_regressors{}_beta{}.png'
                    .format(regress_type, beta), dpi=200)
        plt.close()

    for beta in range(1, 11):
        acquisition = acquisition_rank(y_unk_pred, var_unk_pred, beta=beta)
        print('beta: {}, Kd: {}'.format(beta, y_obs_pred[np.argmax(acquisition)]))

    exit()

def select_candidates(explore=False, **kwargs):
    regressor = kwargs['regressor']
    X_unk = kwargs['X_unk']
    y_unk = kwargs['y_unk']
    idx_unk = kwargs['idx_unk']
    n_candidates = kwargs['n_candidates']

    y_unk_pred = regressor.predict(X_unk)
    var_unk_pred = regressor.uncertainties_

    if explore:
        tprint('Exploring...')
        max_acqs = sorted(set([
            np.argmax(acquisition_rank(y_unk_pred, var_unk_pred, cand))
            for cand in range(1, n_candidates + 1)
        ]))

    else:
        tprint('Exploiting...')
        acquisition = acquisition_rank(y_unk_pred, var_unk_pred)
        max_acqs = np.argsort(-acquisition)[:n_candidates]

    for max_acq in max_acqs:
        if y_unk is None:
            tprint('\tAcquire element {} with predicted Kd value {}'
                   .format(idx_unk[max_acq], y_unk_pred[max_acq]))
        else:
            tprint('\tAcquire element {} with real Kd value {}'
                   .format(idx_unk[max_acq], y_unk[max_acq]))

    return list(max_acqs)

def select_candidates_per_quadrant(explore=False, **kwargs):
    regressor = kwargs['regressor']
    X_unk = kwargs['X_unk']
    y_unk = kwargs['y_unk']
    idx_unk = kwargs['idx_unk']
    n_candidates = kwargs['n_candidates']

    acquired = []

    quad_names = [ 'side', 'repurpose', 'novel' ]

    orig_idx = np.array(list(range(X_unk.shape[0])))

    for quad_name in quad_names:
        if explore:
            tprint('Exploring quadrant {}'.format(quad_name))
        else:
            tprint('Considering quadrant {}'.format(quad_name))

        quad = [ i for i, idx in enumerate(idx_unk)
                 if idx in set(kwargs['idx_' + quad_name]) ]

        idx_unk_quad = [ idx for i, idx in enumerate(idx_unk)
                         if idx in set(kwargs['idx_' + quad_name]) ]

        y_unk_pred = regressor.predict(X_unk[quad])
        var_unk_pred = regressor.uncertainties_

        if explore:
            max_acqs = sorted(set([
                np.argmax(acquisition_rank(y_unk_pred, var_unk_pred, cand))
                for cand in range(1, n_candidates + 1)
            ]))
        else:
            acquisition = acquisition_rank(y_unk_pred, var_unk_pred)
            max_acqs = np.argsort(-acquisition)[:n_candidates]

        for max_acq in max_acqs:
            if y_unk is None:
                tprint('\tAcquire element {} with predicted Kd value {}'
                       .format(idx_unk_quad[max_acq], y_unk_pred[max_acq]))
            else:
                tprint('\tAcquire element {} with real Kd value {}'
                       .format(idx_unk_quad[max_acq], y_unk[quad][max_acq]))

        acquired += list(orig_idx[quad][max_acqs])

    return acquired

def select_candidates_per_protein(**kwargs):
    regressor = kwargs['regressor']
    X_unk = kwargs['X_unk']
    y_unk = kwargs['y_unk']
    idx_unk = kwargs['idx_unk']
    prots = kwargs['prots']

    acquired = []

    orig_idx = np.array(list(range(X_unk.shape[0])))

    for prot_idx, prot in enumerate(prots):
        involves_prot = [ j == prot_idx for i, j in idx_unk ]
        X_unk_prot = X_unk[involves_prot]
        y_unk_prot = y_unk[involves_prot]
        idx_unk_prot = [ (i, j) for i, j in idx_unk if j == prot_idx ]

        y_unk_pred = regressor.predict(X_unk_prot)
        var_unk_pred = regressor.uncertainties_

        acquisition = acquisition_rank(y_unk_pred, var_unk_pred)

        max_acq = np.argmax(acquisition)

        tprint('Protein {}'.format(prot))
        if y_unk is None:
            tprint('\tAcquire element {} with predicted Kd value {}'
                   .format(idx_unk_prot[max_acq], y_unk_pred[max_acq]))
        else:
            tprint('\tAcquire element {} with real Kd value {}'
                   .format(idx_unk_prot[max_acq], y_unk_prot[max_acq]))

        acquired.append(orig_idx[involves_prot][max_acq])

    return acquired

def select_candidates_per_partition(**kwargs):
    regressor = kwargs['regressor']
    X_unk = kwargs['X_unk']
    y_unk = kwargs['y_unk']
    idx_unk = kwargs['idx_unk']
    n_partitions = kwargs['n_candidates']
    chems = kwargs['chems']
    prots = kwargs['prots']
    chem2feature = kwargs['chem2feature']

    if 'partition' in kwargs:
        partition = kwargs['partition']

    else:
        # Partition unknown space using k-means on chemicals.

        from sklearn.cluster import KMeans
        labels = KMeans(
            n_clusters=n_partitions,
            init='k-means++',
            n_init=3,
        ).fit_predict(np.array([
            chem2feature[chem] for chem in chems
        ]))

        partition = []
        for p in range(n_partitions):
            partition.append([
                idx for idx, (i, j) in enumerate(idx_unk)
                if labels[i] == p
            ])

    orig2new_idx = { i: i for i in range(X_unk.shape[0]) }

    for pi in range(len(partition)):
        y_unk_pred = regressor.predict(X_unk[partition[pi]])
        var_unk_pred = regressor.uncertainties_
        partition_pi = set(list(partition[pi]))
        idx_unk_part = [ idx for i, idx in enumerate(idx_unk)
                         if i in partition_pi ]

        acquisition = acquisition_rank(y_unk_pred, var_unk_pred)
        max_acq = np.argmax(acquisition)

        tprint('Partition {}'.format(pi))
        if y_unk is None:
            i, j = idx_unk_part[max_acq]
            chem = chems[i]
            prot = prots[j]
            tprint('\tAcquire {} <--> {} with predicted Kd value {:.3f}'
                   ' and variance {:.3f}'
                   .format(chem, prot, y_unk_pred[max_acq],
                           var_unk_pred[max_acq]))
        else:
            tprint('\tAcquire element {} with real Kd value {}'
                   .format(idx_unk_part[max_acq],
                           y_unk[partition[pi]][max_acq]))

        orig_max_acq = partition[pi][max_acq]
        for i in orig2new_idx:
            if i == orig_max_acq:
                orig2new_idx[i] = None
            elif orig2new_idx[i] is None:
                pass
            elif i > orig_max_acq:
                orig2new_idx[i] -= 1

    # Acquire one point per partition.

    acquired = sorted([ i for i in orig2new_idx if orig2new_idx[i] is None ])
    assert(len(acquired) == n_partitions)

    # Make sure new partition indices match new unknown dataset.

    for pi in range(len(partition)):
        partition[pi] = np.array([
            orig2new_idx[p] for p in partition[pi]
            if orig2new_idx[p] is not None
        ])

    kwargs['partition'] = partition

    return acquired, kwargs

def acquire(**kwargs):
    if 'scheme' in kwargs:
        scheme = kwargs['scheme']
    else:
        scheme = 'exploit'
    if 'n_candidates' in kwargs:
        n_candidates = kwargs['n_candidates']
    else:
        kwargs['n_candidates'] = 1

    if scheme == 'exploit':
        acquired = select_candidates(**kwargs)

    elif scheme == 'explore':
        acquired = select_candidates(explore=True, **kwargs)

    elif scheme == 'quad':
        acquired = select_candidates_per_quadrant(**kwargs)

    elif scheme == 'quadexplore':
        acquired = select_candidates_per_quadrant(explore=True, **kwargs)

    elif scheme == 'perprot':
        acquired = select_candidates_per_protein(**kwargs)

    elif scheme == 'partition':
        acquired, kwargs = select_candidates_per_partition(**kwargs)

    return acquired, kwargs

def iterate(**kwargs):
    prots = kwargs['prots']
    X_obs = kwargs['X_obs']
    y_obs = kwargs['y_obs']
    idx_obs = kwargs['idx_obs']
    X_unk = kwargs['X_unk']
    y_unk = kwargs['y_unk']
    idx_unk = kwargs['idx_unk']
    regressor = kwargs['regressor']
    regress_type = kwargs['regress_type']

    acquired, kwargs = acquire(**kwargs)

    # Reset observations.

    X_acquired = X_unk[acquired]
    y_acquired = y_unk[acquired]

    X_obs = np.vstack((X_obs, X_acquired))
    y_obs = np.hstack((y_obs, y_acquired))
    [ idx_obs.append(idx_unk[a]) for a in acquired ]

    # Reset unknowns.

    unacquired = [ i for i in range(X_unk.shape[0]) if i not in set(acquired) ]

    X_unk = X_unk[unacquired]
    y_unk = y_unk[unacquired]
    idx_unk = [ idx for i, idx in enumerate(idx_unk) if i not in set(acquired) ]

    kwargs['X_obs'] = X_obs
    kwargs['y_obs'] = y_obs
    kwargs['idx_obs'] = idx_obs
    kwargs['X_unk'] = X_unk
    kwargs['y_unk'] = y_unk
    kwargs['idx_unk'] = idx_unk

    return kwargs

if __name__ == '__main__':
    #debug_selection('hybrid')

    param_dict = process()

    param_dict['regress_type'] = sys.argv[1]
    param_dict['scheme'] = sys.argv[2]
    param_dict['n_candidates'] = 10

    if param_dict['scheme'] == 'partition':
        n_iter = 5
    else:
        n_iter = 30

    for i in range(n_iter):
        tprint('Iteration {}'.format(i))

        param_dict = train(**param_dict)

        param_dict = iterate(**param_dict)
