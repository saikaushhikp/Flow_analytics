default:
    @just --list

check:
    conda run -n flow_env python checks/active_pipeline_checks.py

lane date="2025-06-01" start="00" hours="22":
    conda run -n flow_env python regions/brussels/lane_main.py --start-date {{date}} --end-date {{date}} --start-time {{start}} --max-hours {{hours}}

crosswalk date="2025-06-01" start="00" hours="22":
    conda run -n flow_env python regions/brussels/crosswalk_main.py --start-date {{date}} --end-date {{date}} --start-time {{start}} --max-hours {{hours}}

smoke start_date="2025-06-01" end_date="2025-06-01" hours="22":
    conda run -n flow_env python checks/run_brussels_smoke_window.py --start-date {{start_date}} --end-date {{end_date}} --max-hours {{hours}}

irsm-generate date="2025-06-01" start="00" hours="22":
    conda run -n flow_env python irsm/data_generation.py --date {{date}} --start-time {{start}} --max-hours {{hours}}

irsm-iforest:
    conda run -n flow_env python irsm/models/isolation_forest.py

irsm-gaussian:
    conda run -n flow_env python irsm/models/gaussian_anomaly.py

irsm-train:
    conda run -n flow_env python irsm/models/supervised.py --train

irsm-detect:
    conda run -n flow_env python irsm/supervised_detect.py

bhattacharyya date="2025-06-01" hours="22":
    conda run -n flow_env python bhattacharyya/detect.py --date {{date}} --max-hours {{hours}}

compare date="2025-06-01":
    conda run -n flow_env python irsm/compare_mdrac_irsm.py --date {{date}}

summary:
    conda run -n flow_env python checks/summarize_active_results.py

zones:
    conda run -n flow_env python helpers/plot_zones.py --region brussels

heatmaps:
    conda run -n flow_env python helpers/heatmaps.py
