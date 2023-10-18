//this just inits some required variables pulled from html/used between some functions.
let grid;
let dev_type = '', uid = '';
function init(devType, uId) {
  dev_type = devType;
  uid = uId;
}


//create initial table, this uses auto pulled last 30 days
function create_table(columns, data) {
  grid = new gridjs.Grid({
    columns: columns,
    data: data,
    sort: true,
    search: true,
    className: {
      table: 'table-body'
    }
  }).render(document.getElementById("ts-table-div"));

  insert_date_pickers();
}


//update the table, by removing date pickers, 
//force re-rendering the table,and re-add the pickers
//this uses newly pulled data
function update_table(columns, rows) {
  if (grid) {
    remove_date_pickers();

    grid.updateConfig({
      columns: columns,
      data: rows,
      sort: true,
      search: true,
      className: {
        table: 'table-body'
      }
    }).forceRender();
    insert_date_pickers();
  }
}


function get_rows(data) {
  if (!data || typeof data !== "object") return [];

  //this is duplicated and should be passed in tbh
  const columns = ["timestamp", ...Object.keys(data)];
  if (columns.length <= 1) return [];

  const parsed_data = [];
  for (let i = 0; i < data[columns[1]].length; i++) {
    const row = [data[columns[1]][i][0]];
    columns.slice(1).forEach(col_name => {
      if (data[col_name] && data[col_name][i]) row.push(data[col_name][i][1]);
      else row.push(null);
    });
    parsed_data.push(row);
  }
  return parsed_data;
}


function get_cols(data) {
  if (!data || typeof data !== "object") return []

  return columns = ["timestamp", ...Object.keys(data)];
}


//in order to get the date pickers in correctly it seeems to need to be done through JS
//we add them in and set them up here
function insert_date_pickers() {
  const from_picker = document.createElement('input');
  from_picker.type = 'date';
  from_picker.id = 'datepicker-from';
  from_picker.name = 'datepicker-from';
  from_picker.className = 'date-picker ts-date-picker';

  const to_picker = document.createElement('input');
  to_picker.type = 'date';
  to_picker.id = 'datepicker-to';
  to_picker.name = 'datepicker-to';
  to_picker.className = 'date-picker ts-date-picker';

  const go_btn = document.createElement('button');
  go_btn.textContent = 'Go';
  go_btn.className = 'ts-btn';

  //button listener, handles the form
  go_btn.addEventListener('click', function() {
    const from_date = from_picker.value;
    const to_date = to_picker.value;

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
        if (Object.keys(data).length > 0) {
          const columns = get_cols(data);
          const rows = get_rows(data);
          update_table(columns, rows);
        }
      })
      .catch(error => {
        console.error('There was a problem with the fetch operation:', error);
      });
  });
  const grid_js_head = document.querySelector('.gridjs-head');
  grid_js_head.appendChild(from_picker);
  grid_js_head.appendChild(to_picker);
  grid_js_head.appendChild(go_btn);
}


//we need to remove the date pickers when we update table, otherwise it no work
function remove_date_pickers() {
  const datepickerFrom = document.getElementById('datepicker-from');
  const datepickerTo = document.getElementById('datepicker-to');
  const goBtn = document.querySelector('.ts-btn');

  if (datepickerFrom && datepickerTo && goBtn) {
    datepickerFrom.remove();
    datepickerTo.remove();
    goBtn.remove();
  }
}


//helper function to make sure dates chosen are valid
function is_valid_date(dateString) {
  const regex = /^\d{4}-\d{2}-\d{2}$/;
  return regex.test(dateString);
}
