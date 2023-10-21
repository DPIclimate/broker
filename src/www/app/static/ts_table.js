//this just inits some required variables pulled from html/used between some functions.
let grid, dev_type = '', uid = '';
let to_picker_value = new Date();
let from_picker_value = new Date();


function init(devType, uId) {
  dev_type = devType;
  uid = uId;
}


//create initial table, this uses auto pulled last 30 days
function create_table(columns, data) {
  if (grid) return;
  grid = new gridjs.Grid({
    columns: columns,
    data: data,
    sort: true,
    search: true,
    className: {
      table: 'table-body'
    },
    width: '100%'
  }).render(document.getElementById("ts-table-div"));

  insert_date_pickers();
}


//update the table, by removing date pickers, 
//force re-rendering the table,and re-add the pickers
//this uses newly pulled data
function update_table(columns, rows) {
  if (grid) {
    remove_date_pickers();

    //hacky solution, get rid of search to avoid an error, error doesn't do anything
    grid.plugin.remove('search');

    grid.updateConfig({
      columns: columns,
      data: rows,
      sort: true,
      search: true,
      className: {
        table: 'table-body'
      },
      width: '100%'
    }).forceRender();
    insert_date_pickers();
  } else {
    create_table(columns, rows);
  }
}


//in order to get the date pickers in correctly it seeems to need to be done through JS
//we add them in and set them up here
function insert_date_pickers() {
  const from_picker = document.createElement('input');
  from_picker.type = 'date';
  from_picker.id = 'datepicker-from';
  from_picker.name = 'datepicker-from';
  from_picker.className = 'date-picker ts-date-picker';
  from_picker.valueAsDate = from_picker_value;

  const to_picker = document.createElement('input');
  to_picker.type = 'date';
  to_picker.id = 'datepicker-to';
  to_picker.name = 'datepicker-to';
  to_picker.className = 'date-picker ts-date-picker';
  to_picker.valueAsDate = to_picker_value;

  const go_btn = document.createElement('button');
  go_btn.textContent = 'Go';
  go_btn.className = 'ts-btn';

  const csv_export_btn = document.createElement('button');
  csv_export_btn.textContent = 'Export CSV';
  csv_export_btn.className = 'csv-btn';

  //button listener, handles the form
  go_btn.addEventListener('click', function() {
    handle_go_btn(from_picker, to_picker);
  });


  csv_export_btn.addEventListener('click', function() {
    handle_csv_btn();
  });

  const grid_js_head = document.querySelector('.gridjs-head');
  grid_js_head.appendChild(from_picker);
  grid_js_head.appendChild(to_picker);
  grid_js_head.appendChild(go_btn);
  grid_js_head.appendChild(csv_export_btn);
}


//we need to remove the date pickers when we update table, otherwise it no work for some unknown reason
function remove_date_pickers() {
  const date_picker_from = document.getElementById('datepicker-from');
  const date_picker_to = document.getElementById('datepicker-to');
  const go_btn = document.querySelector('.ts-btn');
  const csv_export_btn = document.querySelector('.csv-btn')

  if (date_picker_from) { from_picker_value = date_picker_from.valueAsDate; date_picker_from.remove(); }
  if (date_picker_to) { to_picker_value = date_picker_to.valueAsDate; date_picker_to.remove(); }
  if (go_btn) go_btn.remove();
  if (csv_export_btn) csv_export_btn.remove();
}


function handle_go_btn(from_picker, to_picker) {
  const from_date = from_picker.value;
  const to_date = to_picker.value;
  fetch_and_update_table(from_date, to_date);

}

function fetch_and_update_table(from_date, to_date) {
  if (!is_valid_date(from_date) || !is_valid_date(to_date) || dev_type == '' || uid == '')
    return;

  fetch(`/get_between_dates_ts?dev_type=${dev_type}&uid=${uid}&from_date=${from_date}&to_date=${to_date}`)
    .then(response => {
      if (!response.ok) {
        throw new Error('Network response was not ok');
      }
      return response.json();
    })
    .then(data => {
      update_table(data.columns, data.data);
    })
    .catch(error => {
      console.error('There was a problem with the fetch operation:', error);
    });
}


function handle_csv_btn() {
  const columns = grid.config.columns;

  const last_entry = Array.from(grid.config.pipeline.cache.values()).pop();
  if (!last_entry) {
    return;
  }

  const last_visible_rows = last_entry._rows.map(row => row._cells.map(cell => cell.data));
  const csv_content = [columns.join(','), ...last_visible_rows.map(row => row.join(','))].join('\n');
  const encoded_uri = encodeURI(`data:text/csv;charset=utf-8,${csv_content}`);

  const link = document.createElement('a');
  link.setAttribute('href', encoded_uri);
  link.setAttribute('download', 'table.csv');
  link.click();
}



//helper function to make sure dates chosen are valid
function is_valid_date(dateString) {
  const regex = /^\d{4}-\d{2}-\d{2}$/;
  return regex.test(dateString);
}
