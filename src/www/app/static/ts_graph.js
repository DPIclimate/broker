var chart;
var parsed_data = {} //ugly but things need to access it at varied times
//hopefully 20 different colours should be enough
var GRAPH_COLOURS = [
  "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
  "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
  "#aec7e8", "#ffbb78", "#98df8a", "#ff9896", "#c5b0d5",
  "#c49c94", "#f7b6d2", "#c7c7c7", "#dbdb8d", "#9edae5"
];


//this generates dataset for the chart
//input data only has label, value, timestamp
function generate_datasets(parsed_data) {
  var datasets = [];
  var cindex = 0;

  for (var label in parsed_data) {
    var data = parsed_data[label];
    var colour = GRAPH_COLOURS[cindex++ % GRAPH_COLOURS.length];

    datasets.push({
      label: label,
      data: data.map(entry => ({
        x: entry[0],
        y: entry[1]
      })),
      borderColor: colour,
      backgroundColor: 'rgba(0, 0, 0, 0)',  // Transparent fill
      fill: false
    });
  }
  return datasets;
}

//create the chart via chartjs
function create_chart(parsed_data) {
  parsed_data = parsed_data;
  var ctx = document.getElementById('chart').getContext('2d');
  chart = new Chart(ctx, {
    type: 'line',
    data: {
      datasets: generate_datasets(parsed_data)
    },
    options: {
      scales: {
        x: {
          type: 'time',
          //distribution: 'linear',
          min: luxon.DateTime.now().plus({ days: -30 }).toISODate(),
          max: new Date()
        }
      }
    }
  });
}


function filter_chart(days) {
  chart.options.scales.x.min = luxon.DateTime.now().plus({ days: -days.value }).toISODate();
  chart.options.scales.x.max = new Date();
  chart.update();
}
