let grid;

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
  const columns = ["timestamp", ...Object.keys(data)];
  const parseddata = [];

  for (let i = 0; i < data[columns[1]].length; i++) {
    const row = [data[columns[1]][i][0]];
    columns.slice(1).forEach((colName) => {
      row.push(data[colName][i][1]);
    });
    parseddata.push(row);
  }
  return parseddata
}


function get_cols(data) {
  return columns = ["timestamp", ...Object.keys(data)];
}


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

  go_btn.addEventListener('click', function() {
    const from_date = from_picker.value;
    const to_date = to_picker.value;

    if (!is_valid_date(from_date) || !is_valid_date(to_date))
      return;

    let luid = 1;

    fetch(`/get_between_dates_luid?luid=${luid}&from_date=${from_date}&to_date=${to_date}`)
      .then(response => {
        if (!response.ok) {
          throw new Error('Network response was not ok');
        }
        return response.json();
      })
      .then(data => {
        console.log('daaaaaaaata');
        if (Object.keys(data).length > 0) {
          console.log('daaaaaaaata > 0');
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


function remove_date_pickers() {
  const datepickerFrom = document.getElementById('datepicker-from');
  const datepickerTo = document.getElementById('datepicker-to');
  const goBtn = document.querySelector('.ts-btn'); // Select by class name

  if (datepickerFrom && datepickerTo && goBtn) {
    // Remove all date picker and go button elements from the parent div
    datepickerFrom.remove();
    datepickerTo.remove();
    goBtn.remove();
  }
}


function is_valid_date(dateString) {
  const regex = /^\d{4}-\d{2}-\d{2}$/;
  return regex.test(dateString);
}
