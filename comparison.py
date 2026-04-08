import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from scipy.stats import mannwhitneyu
import warnings
warnings.filterwarnings('ignore')


#load both datasets
ospf = pd.read_csv('./results/ospf_benchmark_results_iterative_ms.csv')
sdn = pd.read_csv('./results/sdn_benchmark_results_iterative_ms.csv')

print(f"OSPF iterations: {len(ospf)}   SDN iterations: {len(sdn)}")