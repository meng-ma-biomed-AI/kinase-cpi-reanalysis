from utils import *

import pandas as pd
import seaborn as sns

def parse_log(model, fname):
    data = []

    if model == 'gp' or model == 'dhybrid':
        uncertainty = 'GP-based uncertainty'
    elif model == 'dmlper5g' or model == 'bayesnn':
        uncertainty = 'Other uncertainty'
    else:
        uncertainty = 'No uncertainty'

    if model == 'gp' or model == 'gp0':
        seed = 1
    else:
        seed = None

    in_data = False
    with open(fname) as f:

        while True:
            line = f.readline()
            if not line:
                break

            if line.startswith('GFP Seed:\t'):
                seed = int(line.rstrip().split()[-1])

            if line.startswith('0\tS'):
                in_data = True

            if in_data:
                assert(seed is not None)
                fields = line.rstrip().split('\t')
                rank = int(fields[0]) + 1
                brightness = float(fields[-1]) + 3.
                data.append([
                    model, uncertainty, rank, brightness, seed,
                ])

            if line.startswith('39899\tS'):
                in_data = False

    return data

if __name__ == '__main__':
    models = [
        'gp',
        #'dhybrid',
        'bayesnn',
        'mlper5g',
        'mlper1',
        'gp0',
    ]

    data = []
    for model in models:
        fname = ('gfp_{}.log'.format(model))
        data += parse_log(model, fname)

    df = pd.DataFrame(data, columns=[
        'model', 'uncertainty', 'order', 'brightness', 'seed',
    ])

    n_leads = [ 5, 50, 500, 5000 ]

    for n_lead in n_leads:
        df_subset = df[df.order <= n_lead]

        plt.figure()
        sns.barplot(x='model', y='brightness', data=df_subset, ci=95,
                    order=models, hue='uncertainty', dodge=False,
                    palette=sns.color_palette("RdBu", n_colors=8,),
                    capsize=0.2,)
        plt.ylim([ 3., 4. ])
        plt.savefig('figures/gfp_lead_{}.svg'.format(n_lead))
        plt.close()

        gp_brights = df_subset[df_subset.model == 'gp'].brightness
        for model in models:
            if model == 'gp':
                continue
            other_brights = df_subset[df_subset.model == model].brightness
            print('{} leads, t-test, GP vs {}:'.format(n_lead, model))
            print('\tt = {:.4f}, P = {:.4g}'
                  .format(*ss.ttest_ind(gp_brights, other_brights,
                                        equal_var=False)))
        print('')


    plt.figure()
    for model in models:
        df_subset = df[(df.model == model) & (df.seed == 1)]
        order = np.array(df_subset.order).ravel()
        brightness = np.array(df_subset.brightness).ravel()

        order_idx = np.argsort(order)
        order = order[order_idx]
        brightness = brightness[order_idx]

        n_positive, n_positives = 0, []
        for i in range(len(order)):
            if brightness[i] > 3:
                n_positive += 1
            n_positives.append(n_positive)
        plt.plot(order, n_positives)
    frac_positive = sum(brightness > 3) / float(len(brightness))
    plt.plot(order, frac_positive * order, c='gray', linestyle='--')
    plt.legend(models + [ 'Random guessing' ])
    plt.savefig('figures/gfp_acquisition.svg')#, dpi=300)