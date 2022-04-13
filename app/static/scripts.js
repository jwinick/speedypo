function todaysDate(){
    var d = new Date();
    var month = d.getMonth();
    var month_actual = month + 1;

    if (month_actual < 10) {
      month_actual = "0"+month_actual;
      }

    var day_val = d.getDate();
    if (day_val < 10) {
      day_val = "0"+day_val;
      }

    return(d.getFullYear()+"-"+ month_actual +"-"+day_val)
}

function removeOrder(order_id){
    return new Promise((resolve,reject) => {
        $.ajax({
                type: 'POST',
                url : "{{ url_for('main.remove_order') }}",
                contentType: 'application/json;charset=UTF-8',
                data: JSON.stringify({'order_id':order_id},null,'\t'),
                success: function(result){
                  resolve(result)
                },
                error: function (error) {
                  reject(error)
                }
              })

})}


function displayDate(string){
    string = new Date(string);
    var month = string.getMonth()+1;
    var day = string.getDate();
    var year = string.getFullYear().toString().substr(-2);
    var output = month+"-"+day+"-"+year
    return output
    };

function buildRow(end){
    if(!Number.isInteger(end)){
        console.log("buildRow function requires an integer!");
    }else{
        array = new Array()
        for(j=2;j<=end;j++){
            var number = j.toString();
            string = 'html_'.concat(number);
            array.push(string);
        };
        var html = array.join(',')
        var html = 'html_1.concat('+html+')'
        return html
    }
};

function pretty_variable(ugly_variable){
    var all_caps = ['sku','id','mabd']
    var words = ugly_variable.split("_");
    for(j=0;j<words.length;j++){
        if(all_caps.includes(words[j])){
            words[j] = words[j].toUpperCase();
        }else{
            words[j]=words[j][0].toUpperCase() + words[j].substr(1);
        };

    };
    return words.join(' ')
};

order_variables = (function(){
    return ['order_number','order_id','supplier_id','supplier_name','company_name','sku_id','sku_name','quantity','supplier_email','sku_count','created_date','mabd_date','last_ordered_date','order_count'];
});

function formatSectionMoney(section){
    $('#'+section).find('.money').each(function(){
        value = $(this).html()
        value = currency(value).format()
        $(this).html(String(value))
    })
}

function formatMoney(){

    $('.money').each(function(){
        value = $(this).html()
        value = currency(value).format()

        $(this).html(String(value))
    })
}

function construct_table(data,primary_key){

    var variables = Object.keys(data[0]);

    console.log(variables)

    var order = order_variables();

    console.log(order)

    variables.sort(function(a, b){
        return order.indexOf(a) - order.indexOf(b);
    });

    console.log(variables)

    //console.log(variables)
    //build delete header
    ///function for deleting row

    //build table head
    let variable_html = [];

    var action_header = "<th class='action'>Action</th>"
    let pretty_variables = [];

    //loop through variables to create headers
    for(i=0;i<variables.length;i++){
        var ugly = variables[i];
        var pretty = pretty_variable(ugly)

        pretty_variables.push(pretty)

        var html = "<th class='"+ugly+"'>"+pretty+'</th>';


        variable_html.push(html);

    };

    // assemble thead html
    var head = "<thead>"+ action_header + variable_html.join('') + "</thead>";

    // build table body
    var data_length = data.length;
    let body_html = [];

    var delete_type = primary_key.replace('_id','')
    var delete_type = delete_type[0].toUpperCase() + delete_type.substr(1);

    //console.log(data)
    for(i=0;i<data_length;i++){
        var row = data[i];

        var columns = [];

        var action_column_array = [];
        action_column_array.push("<td class='action' id='");
        action_column_array.push(String(row[primary_key]));
        action_column_array.push("'>");

        action_column_array.push('<div class="dropdown"><button class="btn btn-default dropdown-toggle" type="button" id="dropdownMenuButton2" data-bs-toggle="dropdown" aria-expanded="false"><span class="glyphicon glyphicon-cog" aria-hidden="true"></span></button><ul class="dropdown-menu dropdown-menu-dark" aria-labelledby="dropdownMenuButton2"><li><a class="dropdown-item" href="javascript:;" onclick="edit');

        action_column_array.push(delete_type);
        action_column_array.push('(');
        action_column_array.push(String(row[primary_key]));
        action_column_array.push(')">Edit</a></li><li><hr class="dropdown-divider"></li><li><a class="dropdown-item" href="javascript:;" onclick="remove');
        action_column_array.push(delete_type);
        action_column_array.push('(');
        action_column_array.push(String(row[primary_key]));
        action_column_array.push(')"><span class="glyphicon glyphicon-trash" aria-hidden="true"></span> Delete</a></li></ul></div>');


        action_column_array.push("</td>");
        var action_column = action_column_array.join('');
        columns.push(action_column);


        //console.log(variables)
        for(j=0;j<variables.length;j++){
            //console.log("Variables: "+variables[j])
            if(variables[j] == 'order_number'){

                var order_id = String(row['order_id'])
                var access_code = String(row['access_code'])

                var column_array = [];


                column_array.push("<td class='");
                column_array.push(variables[j]);
                column_array.push("'><a ");
                column_array.push("href='view-po/"+order_id+"/");
                column_array.push(access_code);
                column_array.push("'>");
                column_array.push(String(row[variables[j]]));
                column_array.push("</a></td>")
                var column = column_array.join('');
                columns.push(column);
            // }else if(variables[j].endsWith('_id') == true){
            //     var href_template = variables[j].replace('_id','');
            //     var href_variable = variables[j]
            //     var href = String(row[href_variable])
            //     var column_array = [];


            //     column_array.push("<td class='");
            //     column_array.push(variables[j]);
            //     column_array.push("'><a ");
            //     column_array.push("href='/"+href_template+"/");
            //     column_array.push(href);
            //     column_array.push("'>");
            //     column_array.push(String(row[variables[j]]));
            //     column_array.push("</a></td>")
            //     var column = column_array.join('');
            //     columns.push(column);

            }else if(variables[j].endsWith('_date') == true){
                var date_string = String(row[variables[j]]);
                try{
                    var date = displayDate(date_string);
                }catch{
                    var date = ''
                };
                var column_array = [];
                column_array.push("<td class='");
                column_array.push(variables[j]);
                column_array.push("'>")
                column_array.push(date);
                column_array.push('</td>');
                var column = column_array.join('');
                columns.push(column);
            }else{
                var column_array = [];
                column_array.push("<td class='");
                column_array.push(variables[j]);
                column_array.push("'>")
                column_array.push(String(row[variables[j]]));
                column_array.push('</td>');
                var column = column_array.join('');
                columns.push(column);
            };
            };

            var row_html = '<tr>'+columns.join('')+'</tr>';
            body_html.push(row_html)
    };


    var body = '<tbody>'+body_html.join('')+'</tbody>'

   // var body = '<tbody id="rows"></tbody>'

    //combine thead and tbody
    var html = '<table id="data_table" class="table table-striped table-hover " border="1">'+head+body+'</table>';

    if(data_length > 0){
        $('#table_container > #table_data').html(html);
        $('#table_container').removeClass('hidden');
    };


    return 'Great success'

};

function pagination(per_page,page,data_length){

    if(per_page>data_length){
        var quo = 1;
    }else{
        var quo = Math.ceil(data_length/per_page);
    };


    var prev_page = parseInt(page)-1
    var previous_page = prev_page.toString()

    var meat = [];

    for(i=0;i<quo;i++){
        var numb = i+1;
        if(numb==page){
            var html = '<p class="pag active">'+numb+'</p>';
        }else{
            var html = '<p class="pag">'+numb+'</p>';
        };
        meat.push(html)
    };

    var pagination_html = meat.join('');


    var next_page = parseInt(page)+1
    var next_page = next_page.toString()

    var whole = data_length.toString();

    var start = 1+(page-1)*per_page;

    var end = page*per_page;
    if(end > data_length){
        var end = data_length;
    };

    var rows_html = 'Showing '+start+'-'+end+' of '+whole;

    return {'pagination_html':pagination_html,'rows_html':rows_html}

};
