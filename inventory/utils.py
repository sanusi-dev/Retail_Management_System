def has_any_children(product):
    product_child_list = [
        "purchase_order_items",
        "receipt_items_as_product",
        "receipt_items_as_actual_product",
        "sale_items",
        "variants",
        "inventories",
        "serialized_products",
        "boxed_products",
        "coupled_products",
    ]

    for child in product_child_list:
        if hasattr(product, child) and getattr(product, child).exists():
            return True
    return False


# {% comment %} {% extends "index.html" %}
# {% load static %}
# {% block content %}
#     {% include "partials/spinner.html" with id="body_spinner" %}
#     <div class="flex h-full flex-col" id="main_body">
#         {% block header %}
#             <div class="h-16 flex items-center justify-between px-4">
#                 {% include "partials/table_filter.html" with view_name="All Products" %}
#                 <a href="{% url 'add_product' %}" hx-boost="true" hx-target="#main_body" hx-indicator="#body_spinner" hx-vals='js:{ "next": window.location.pathname + window.location.search }' class="px-3 py-2 text-sm font-medium text-center inline-flex items-center text-white bg-brand-500 rounded-md hover:bg-blue-600 focus:ring-1 focus:outline-none focus:ring-blue-200">
#                     <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="size-5">
#                         <path d="M10.75 4.75a.75.75 0 0 0-1.5 0v4.5h-4.5a.75.75 0 0 0 0 1.5h4.5v4.5a.75.75 0 0 0 1.5 0v-4.5h4.5a.75.75 0 0 0 0-1.5h-4.5v-4.5Z" />
#                     </svg>
#                     New
#                 </a>
#             </div>
#         {% endblock header %}
#         {% block body %}
#             <div id="table_container">
#                 <div class="flex-1 overflow-auto pb-16">
#                     <table class="w-full text-sm text-left text-gray-500">
#                         <thead class="text-xs text-gray-500 font-normal uppercase bg-gray-50 sticky top-0 z-10">
#                             <tr class="border-t border-b">
#                                 <th scope="col" class="px-6 py-3">Name</th>
#                                 <th scope="col" class="px-6 py-3">SKU</th>
#                                 <th scope="col" class="px-6 py-3">Category</th>
#                                 <th scope="col" class="px-6 py-3">Stock on Hand</th>
#                             </tr>
#                         </thead>
#                         <tbody class="text-sm text-black font-light" id="tbody">
#                             {% if products %}
#                                 {% for product in products %}
#                                     <tr class="bg-white border-b border-gray-100 hover:bg-gray-50 cursor-pointer" hx-get="{{ product.get_absolute_url }}" hx-target="#main_body" hx-indicator="#body_spinner" hx-push-url="true" hx-vals='js:{ "next": window.location.pathname + window.location.search }'>
#                                         <td class="px-6 py-3 capitalize">{{ product.modelname|upper }}</td>
#                                         <td class="px-6 py-3 capitalize">{{ product.sku|upper }}</td>
#                                         <td class="px-6 py-3 capitalize">{{ product.category }}</td>
#                                         <td class="px-6 py-3 capitalize">{{ product.stock_on_hand }}</td>
#                                     </tr>
#                                 {% endfor %}
#                             {% else %}
#                                 <tr class="bg-white border-b border-gray-100 hover:bg-gray-50">
#                                     <td colspan="4" class="px-6 py-3 text-center">
#                                         <p>No products available.</p>
#                                     </td>
#                                 </tr>
#                             {% endif %}
#                         </tbody>
#                     </table>
#                 </div>
#                 <div class="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 p-2 z-10">
#                     <div class="flex justify-end">
#                         {% include 'partials/pagination.html' with page_obj=products target="table_container" %}
#                     </div>
#                 </div>
#             </div>
#         {% endblock body %}
#     </div>
# {% endblock content %} {% endcomment %}
