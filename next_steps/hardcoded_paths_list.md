Command to find hardcoded paths in the codebase:
```bash
grep -Rn "/home/ubuntu/prem" .
```

OUTPUT(excluded the files in `next_steps/`and `docs/` since they are needed for historical validation.Excluded the files in `vlm/` since they are already marked for deprecation):

```bash
./plotter.py:525:        ...     csv_path='/home/ubuntu/prem/results/brussels/mdrac/01/mdrac_01.csv',
./plotter.py:528:        # Creates: /home/ubuntu/prem/results/brussels/mdrac/01/plots/11520140_11520195/
./plotter.py:529:        #          /home/ubuntu/prem/results/brussels/mdrac/01/plots/11531151_11531576/
./plotter.py:660:    CSV_PATH = '/home/ubuntu/prem/results/brussels/mdrac/14/mdrac_14.csv'
./README.md:56:cd /home/ubuntu/prem
./README.md:62:cd /home/ubuntu/prem
./README.md:68:cd /home/ubuntu/prem
./README.md:74:cd /home/ubuntu/prem
./utils/irsm_preprocessing.py:52:        config = load_config('/home/ubuntu/prem/config.yaml')
./irsm/irsm_plotter.py:19:sys.path.insert(0, '/home/ubuntu/prem')
./irsm/irsm_plotter.py:587:    with open('/home/ubuntu/prem/irsm/irsm_config.yaml', 'r') as f:
./irsm/irsm_plotter.py:594:    csv_path = f'/home/ubuntu/prem/irsm/results/{region}/{date}/lanes_detections.csv'
./irsm/irsm_plotter.py:596:    output_dir = f'/home/ubuntu/prem/irsm/results/{region}/{date}/plots'
./irsm/irsm_config.yaml:11:  output_base: '/home/ubuntu/prem/irsm'
./irsm/supervised_detect.py:12:sys.path.insert(0, '/home/ubuntu/prem')
./irsm/supervised_detect.py:24:DATA_PATH = '/home/ubuntu/prem/irsm/data/brussels/2025-06-01/lanes.csv'
./irsm/supervised_detect.py:27:OUTPUT_DIR = '/home/ubuntu/prem/irsm/results/brussels/2025-06-01'
./irsm/models/gaussian_anomaly.py:12:sys.path.insert(0, '/home/ubuntu/prem')
./irsm/models/gaussian_anomaly.py:291:    config = load_irsm_config('/home/ubuntu/prem/irsm/irsm_config.yaml')
./irsm/models/gaussian_anomaly.py:297:    data_path = f'/home/ubuntu/prem/irsm/data/{region}/{date}/lanes.csv'
./irsm/models/gaussian_anomaly.py:298:    output_dir = f'/home/ubuntu/prem/irsm/results/{region}/{date}'
./irsm/models/isolation_forest.py:15:sys.path.insert(0, '/home/ubuntu/prem')
./irsm/models/isolation_forest.py:36:    config = load_irsm_config('/home/ubuntu/prem/irsm/irsm_config.yaml')
./irsm/models/supervised.py:16:sys.path.insert(0, '/home/ubuntu/prem')
./irsm/models/supervised.py:54:DATA_DIR = '/home/ubuntu/prem/irsm/data/supervised'
./irsm/models/supervised.py:329:        config = load_irsm_config('/home/ubuntu/prem/irsm/irsm_config.yaml')
./irsm/visualize_risk.py:12:sys.path.insert(0, '/home/ubuntu/prem')
./irsm/visualize_risk.py:208:    config = load_irsm_config('/home/ubuntu/prem/irsm/irsm_config.yaml')
./irsm/visualize_risk.py:214:    data_path = f'/home/ubuntu/prem/irsm/data/{region}/{date}/lanes.csv'
./irsm/visualize_risk.py:215:    detections_path = f'/home/ubuntu/prem/irsm/results/{region}/{date}/lanes_detections.csv'
./irsm/visualize_risk.py:216:    output_dir = f'/home/ubuntu/prem/irsm/results/{region}/{date}/visualizations'
./plot_zones.py:12:sys.path.insert(0, '/home/ubuntu/prem')
./config.yaml:198:    base_results: "/home/ubuntu/prem/results/brussels/mdrac"
./regions/oulu/main.ipynb:20:    "sys.path.insert(0, '/home/ubuntu/prem')\n",
./regions/oulu/main.ipynb:90:    "OUTPUT_DIR = \"/home/ubuntu/prem/results\"\n",
./regions/oulu/main.ipynb:92:    "config = load_config(\"/home/ubuntu/prem/config.yaml\")\n",
./regions/oulu/main.ipynb:1391:      "✓ Saved lane conflicts to: /home/ubuntu/prem/results/oulu/mdrac_lanes/mdrac_lanes_2025-08-22_to_2025-09-11.csv\n",
./regions/oulu/main.ipynb:1392:      "✓ Saved lane statistics to: /home/ubuntu/prem/results/oulu/mdrac_lanes/lane_stats_2025-08-22_to_2025-09-11.csv\n"
./regions/oulu/lane_main.py:6:sys.path.insert(0, '/home/ubuntu/prem')
./regions/oulu/lane_main.py:44:config = load_config("/home/ubuntu/prem/config.yaml")
./regions/oulu/analyze_nearmiss_oulu.ipynb:11:    "sys.path.insert(0, '/home/ubuntu/prem')\n",
./regions/oulu/analyze_nearmiss_oulu.ipynb:842:    "results_base = Path(\"/home/ubuntu/prem/results/oulu\")\n",
./regions/oulu/crosswalk_main.py:6:sys.path.insert(0, '/home/ubuntu/prem')
./regions/oulu/crosswalk_main.py:47:config = load_config("/home/ubuntu/prem/config.yaml")
./regions/brussels/main.ipynb:27:    "sys.path.insert(0, '/home/ubuntu/prem')\n",
./regions/brussels/main.ipynb:81:    "OUTPUT_DIR = \"/home/ubuntu/prem/results\"\n",
./regions/brussels/main.ipynb:83:    "config = load_config(\"/home/ubuntu/prem/config.yaml\")\n",
./regions/brussels/main.ipynb:594:      "✓ Saved 3 conflicts to /home/ubuntu/prem/results/brussels/mdrac/14/mdrac_14.csv\n",
./regions/brussels/main.ipynb:595:      "Saved to /home/ubuntu/prem/results/brussels/mdrac/14/mdrac_14.csv\n"
./regions/brussels/postprocessing.ipynb:32:    "sys.path.insert(0, '/home/ubuntu/prem')\n",
./regions/brussels/postprocessing.ipynb:61:      "  M-DRAC input: /home/ubuntu/prem/regions/brussels/results/brussels/mdrac/04/mdrac_04.csv\n",
./regions/brussels/postprocessing.ipynb:62:      "  Output: /home/ubuntu/prem/regions/brussels/results/brussels\n"
./regions/brussels/postprocessing.ipynb:68:    "config = load_config(\"/home/ubuntu/prem/config.yaml\")\n",
./regions/brussels/postprocessing.ipynb:74:    "RESULTS_DIR = \"/home/ubuntu/prem/regions/brussels/results\"\n",
./regions/brussels/postprocessing.ipynb:413:      "✓ Saved 5 conflicts to /home/ubuntu/prem/regions/brussels/results/brussels/brussels/mdrac_postprocessed/04/mdrac_postprocessed_04.csv\n",
./regions/brussels/postprocessing.ipynb:416:      "  Output: /home/ubuntu/prem/regions/brussels/results/brussels/brussels/mdrac_postprocessed/04/mdrac_postprocessed_04.csv\n",
./regions/brussels/lane_main.py:7:sys.path.insert(0, '/home/ubuntu/prem')
./regions/brussels/lane_main.py:47:config = load_config("/home/ubuntu/prem/config.yaml")
./regions/brussels/analyze_nearmiss.ipynb:11:    "sys.path.insert(0, '/home/ubuntu/prem')\n",
./regions/brussels/analyze_nearmiss.ipynb:60:    "# results_dir = Path(\"/home/ubuntu/prem/results/brussels/mdrac\")\n",
./regions/brussels/analyze_nearmiss.ipynb:408:    "results_base = Path(\"/home/ubuntu/prem/results/brussels\")\n",
./regions/brussels/analyze_nearmiss.ipynb:1105:      "✓ Saved daily statistics to /home/ubuntu/prem/results/brussels/analysis/daily_nearmiss_stats.csv\n"
./regions/brussels/analyze_nearmiss.ipynb:1112:      "✓ Saved heatmap to /home/ubuntu/prem/results/brussels/analysis/risk_heatmap.png\n"
./regions/brussels/analyze_nearmiss.ipynb:1118:    "output_path = Path(\"/home/ubuntu/prem/results/brussels/analysis\")\n",
./regions/brussels/crosswalk_main.py:6:sys.path.insert(0, '/home/ubuntu/prem')
./regions/brussels/crosswalk_main.py:44:config = load_config("/home/ubuntu/prem/config.yaml")
```