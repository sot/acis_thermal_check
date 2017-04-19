================================
{{proc.name}} temperatures check
================================
.. role:: red

{% if proc.errors %}
Processing Errors
-----------------
.. class:: red
{% endif %}

Summary
--------         
.. class:: borderless

=====================  =============================================
Date start             {{proc.datestart}}
Date stop              {{proc.datestop}}
{{proc.msid}} status     {%if viols.default%}:red:`NOT OK`{% else %}OK{% endif%} (Planning Limit = {{"%.1f"|format(proc.msid_limit)}} C)
{% if oflsdir %}
Load directory         {{oflsdir}}
{% endif %}
Run time               {{proc.run_time}} by {{proc.run_user}}
Run log                `<run.dat>`_
Temperatures           `<temperatures.dat>`_
States                 `<states.dat>`_
=====================  =============================================

{% if viols.default  %}
{{proc.msid}} Violations
------------------------
=====================  =====================  ==================
Date start             Date stop              Max temperature
=====================  =====================  ==================
{% for viol in viols.default %}
{{viol.datestart}}  {{viol.datestop}}  {{"%.2f"|format(viol.maxtemp)}}
{% endfor %}
=====================  =====================  ==================
{% else %}
No {{proc.msid}} Violations
{% endif %}

.. image:: {{plots.default.filename}}
.. image:: {{plots.pow_sim.filename}}

==============================
{{proc.name}} Model Validation
==============================

MSID quantiles
---------------

Note: {{proc.name}} quantiles are calculated using only points where {{proc.msid}} > {{proc.hist_limit.0}} degC.

.. csv-table:: 
   :header: "MSID", "1%", "5%", "16%", "50%", "84%", "95%", "99%"
   :widths: 15, 10, 10, 10, 10, 10, 10, 10

{% for plot in plots_validation %}
{% if plot.quant01 %}
   {{plot.msid}},{{plot.quant01}},{{plot.quant05}},{{plot.quant16}},{{plot.quant50}},{{plot.quant84}},{{plot.quant95}},{{plot.quant99}}
{% endif %}
{% endfor%}

{% if valid_viols %}
Validation Violations
---------------------

.. csv-table:: 
   :header: "MSID", "Quantile", "Value", "Limit"
   :widths: 15, 10, 10, 10

{% for viol in valid_viols %}
   {{viol.msid}},{{viol.quant}},{{viol.value}},{{"%.2f"|format(viol.limit)}}
{% endfor%}

{% else %}
No Validation Violations
{% endif %}


{% for plot in plots_validation %}
{{ plot.msid }}
-----------------------

{% if proc.hist_limit|length == 2 %}
Note: {{proc.name}} residual histograms include points where {{proc.msid}} > {{proc.hist_limit.0}} degC in blue and points where {{proc.msid}} > {{proc.hist_limit.1}} degC in red.
{% else %}
Note: {{proc.name}} residual histograms include only points where {{proc.msid}} > {{proc.hist_limit.0}} degC.
{% endif %}

Red = telemetry, blue = model

.. image:: {{plot.lines}}
.. image:: {{plot.histlog}}
.. image:: {{plot.histlin}}

{% endfor %}
