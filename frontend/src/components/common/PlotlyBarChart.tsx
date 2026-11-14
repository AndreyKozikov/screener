import Plotly from 'plotly.js/lib/core';
import * as bar from 'plotly.js/lib/bar';
import createPlotlyComponent from 'react-plotly.js/factory';

Plotly.register([bar]);

const Plot = createPlotlyComponent(Plotly);

export default Plot;
