# from django.db import models
# import uuid
# from inventory.models import Product
# from account.models import CustomUser
# from django.utils import timezone


# class PurchaseOrder(models.Model):
#     class Status(models.TextChoices):
#         PENDING = "pending", "Pending"
#         PARTIALLY_RECEIVED = "partially received", "Partially Received"
#         RECEIVED = "received", "Received"
#         CANCELLED = "cancelled", "Cancelled"

#     def gen_po_number():
#         return f"PO-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

#     po_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
#     supplier = models.ForeignKey(
#         Supplier, on_delete=models.PROTECT, related_name="purchase_orders"
#     )
#     po_number = models.CharField(
#         max_length=50, editable=False, unique=True, default=gen_po_number
#     )
#     order_date = models.DateTimeField(auto_now_add=True)
#     delivery_date = models.DateTimeField(null=True, blank=True)
#     status = models.CharField(max_length=20, choices=Status, default=Status.PENDING)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now_add=True)
#     created_by = models.ForeignKey(
#         CustomUser,
#         on_delete=models.SET_NULL,
#         blank=True,
#         null=True,
#         related_name="created_%(class)s_set",
#     )
#     updated_by = models.ForeignKey(
#         CustomUser,
#         on_delete=models.SET_NULL,
#         blank=True,
#         null=True,
#         related_name="updated_%(class)s_set",
#     )


# class PurchaseOrderItem(models.Model):
#     class Status(models.TextChoices):
#         ACTIVE = "active", "Active"
#         PENDING = "pending", "Pending"
#         APPROVED = "approved", "Approved"
#         PARTIALLY_RECEIVED = "partially received", "Partially Received"
#         RECEIVED = "received", "Received"
#         CANCELLED = "cancelled", "Cancelled"

#     po_item_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
#     purchase_order = models.ForeignKey(
#         PurchaseOrder, on_delete=models.CASCADE, related_name="po_items"
#     )
#     product = models.ForeignKey(
#         Product, on_delete=models.PROTECT, related_name="po_items"
#     )
#     ordered_quantity = models.IntegerField()
#     unit_price_at_order = models.DecimalField(max_digits=10, decimal_places=2)
#     status = models.CharField(max_length=20, choices=Status, default=Status.PENDING)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now_add=True)
#     created_by = models.ForeignKey(
#         CustomUser,
#         on_delete=models.SET_NULL,
#         blank=True,
#         null=True,
#         related_name="created_%(class)s_set",
#     )
#     updated_by = models.ForeignKey(
#         CustomUser,
#         on_delete=models.SET_NULL,
#         blank=True,
#         null=True,
#         related_name="updated_%(class)s_set",
#     )

   <div class="flex p-4">
      <div class="p-6 w-full max-w-4xl">
         <form action="{% url 'process_order' %}" method="post">
            {% csrf_token %}
            <h1 class="text-xl mb-10">New Purchase Order</h1>
            <div class="w-[80%]">
               <div class="grid grid-cols-[1fr_2fr_50px] mb-6 items-center">
                  {% if po_form.non_field_errors %}
                     <div class="sm:col-span-2 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative"
                          role="alert">
                        {% for error in po_form.non_field_errors %}
                           <div class="flex items-center p-4 mb-4 text-sm text-red-600 border border-red-200 rounded-lg bg-red-50 dark:bg-gray-600 dark:text-red-300 dark:border-red-800"
                                role="alert">
                              <svg class="shrink-0 inline w-4 h-4 me-3"
                                   aria-hidden="true"
                                   xmlns="http://www.w3.org/2000/svg"
                                   fill="currentColor"
                                   viewBox="0 0 20 20">
                                 <path d="M10 .5a9.5 9.5 0 1 0 9.5 9.5A9.51 9.51 0 0 0 10 .5ZM9.5 4a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3ZM12 15H8a1 1 0 0 1 0-2h1v-3H8a1 1 0 0 1 0-2h2a1 1 0 0 1 1 1v4h1a1 1 0 0 1 0 2Z" />
                              </svg>
                              <span class="sr-only">Info</span>
                              <div>
                                 <span class="font-medium">An error has occured!</span> {{ error }}
                              </div>
                           </div>
                        {% endfor %}
                     </div>
                  {% endif %}
                  <div>
                     <label for="{{ po_form.field.id_for_label }}"
                            class="block text-sm font-medium text-red-600">{{ po_form.supplier.label }}</label>
                  </div>
                  <div class="flex items-center">
                     {{ po_form.supplier }}
                     {% if po_form.supplier.errors %}<p>{{ po_form.supplier.errors }}</p>{% endif %}
                  </div>
                  <a href="{% url 'add_supplier' %}?next={{ request.path }}"
                     class="border rounded-r-md p-2 flex items-center justify-center h-full bg-blue-500 text-white hover:bg-blue-600">
                     <svg xmlns="http://www.w3.org/2000/svg"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke-width="1.5"
                          stroke="currentColor"
                          class="w-6 h-6">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                     </svg>
                  </a>
               </div>
            </div>
            <div class="my-10">
               <h2 class="text-lg mb-2 bg-gray-100">Item Table</h2>
               <div class="overflow-x-auto">
                  <table class="w-full">
                     <thead>
                        <tr class="bg-gray-100">
                           <th class="p-2 text-left">Product</th>
                           <th class="p-2 text-left">Quantity</th>
                           <th class="p-2 text-left">Unit Price</th>
                           <th class="p-2"></th>
                        </tr>
                     </thead>
                     <tbody id="items-container">
                        {% for form in item_forms %}
                           {% if form.non_field_errors %}
                              {% for error in form.non_field_errors %}
                                 <div class="flex items-center p-1 mb-4 text-sm text-red-800 border border-red-300 rounded-lg bg-red-50 dark:bg-gray-800 dark:text-red-400 dark:border-red-800"
                                      role="alert">
                                    <svg class="shrink-0 inline w-4 h-4 me-3"
                                         aria-hidden="true"
                                         xmlns="http://www.w3.org/2000/svg"
                                         fill="currentColor"
                                         viewBox="0 0 20 20">
                                       <path d="M10 .5a9.5 9.5 0 1 0 9.5 9.5A9.51 9.51 0 0 0 10 .5ZM9.5 4a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3ZM12 15H8a1 1 0 0 1 0-2h1v-3H8a1 1 0 0 1 0-2h2a1 1 0 0 1 1 1v4h1a1 1 0 0 1 0 2Z" />
                                    </svg>
                                    <span class="sr-only">Info</span>
                                    <div>
                                       <span class="font-medium">An error has occured!</span> {{ error }}
                                    </div>
                                 </div>
                              {% endfor %}
                           {% endif %}
                           {% include "supply_chain/po_orders/partials/item_form.html" with form=form prefix=form.prefix %}
                        {% endfor %}
                     </tbody>
                  </table>
               </div>
               <div class="bg-gray-100 pl-2">
                  <button type="button"
                          hx-get="{% url 'add_item' %}"
                          hx-target="#items-container"
                          hx-swap="beforeend"
                          class="text-blue-600 my-2">Add New Row</button>
               </div>
            </div>
            <!-- Actions -->
            <div class="mt-6 flex space-x-4">
               <button type="submit"
                       class="text-white bg-blue-500 hover:bg-blue-600 focus:ring-2 focus:ring-blue-300 font-medium rounded-lg text-sm px-5 py-2 me-2 mb-2 dark:bg-blue-600 dark:hover:bg-blue-600 focus:outline-none dark:focus:ring-blue-600">
                  Save
               </button>
               <a href="{% url 'po_order' %}"
                  class="py-2 px-4.5 me-2 mb-2 text-sm font-medium text-gray-900 focus:outline-none bg-white rounded-lg border border-gray-200 hover:bg-gray-100 hover:text-blue-700 focus:z-10 focus:ring-2 focus:ring-gray-100 dark:focus:ring-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:border-gray-600 dark:hover:text-white dark:hover:bg-gray-700">
                  Cancel
               </a>
            </div>
         </form>
      </div>
   </div>


<button type="button"
                          hx-get=""
                          hx-target=""
                          hx-swap=""
                          class="text-blue-600 my-2">Add New Row</button>








{% extends 'index.html' %}
{% load static %}
{% block content %}
   <div class="flex p-4">
      <div class="p-6 w-full max-w-4xl">
         <form method="post">
            {% csrf_token %}
            <h1 class="text-xl mb-10">New Purchase Order</h1>
            <div class="w-[80%]">
               <div class="grid grid-cols-[1fr_2fr_50px] mb-6 items-center">
                  {% comment %} Purchase order error {% endcomment %}
                  {% if form.non_field_errors %}
                     <div class="sm:col-span-2 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative"
                          role="alert">
                        {% for error in form.non_field_errors %}
                           <div class="flex items-center p-4 mb-4 text-sm text-red-600 border border-red-200 rounded-lg bg-red-50 dark:bg-gray-600 dark:text-red-300 dark:border-red-800"
                                role="alert">
                              <svg class="shrink-0 inline w-4 h-4 me-3"
                                   aria-hidden="true"
                                   xmlns="http://www.w3.org/2000/svg"
                                   fill="currentColor"
                                   viewBox="0 0 20 20">
                                 <path d="M10 .5a9.5 9.5 0 1 0 9.5 9.5A9.51 9.51 0 0 0 10 .5ZM9.5 4a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3ZM12 15H8a1 1 0 0 1 0-2h1v-3H8a1 1 0 0 1 0-2h2a1 1 0 0 1 1 1v4h1a1 1 0 0 1 0 2Z" />
                              </svg>
                              <span class="sr-only">Info</span>
                              <div>
                                 <span class="font-medium">An error has occured!</span> {{ error }}
                              </div>
                           </div>
                        {% endfor %}
                     </div>
                  {% endif %}
                  {% comment %} Purchase order error end {% endcomment %}
                  <div>
                     <label for="{{ form.field.id_for_label }}"
                            class="block text-sm font-medium text-red-600">{{ form.supplier.label }}</label>
                  </div>
                  <div class="flex items-center">
                     {{ form.supplier }}
                     {% if form.supplier.errors %}<p>{{ form.supplier.errors }}</p>{% endif %}
                  </div>
                  <a href="{% url 'add_supplier' %}?next={{ request.path }}"
                     class="border rounded-r-md p-2 flex items-center justify-center h-full bg-blue-500 text-white hover:bg-blue-600">
                     <svg xmlns="http://www.w3.org/2000/svg"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke-width="1.5"
                          stroke="currentColor"
                          class="w-6 h-6">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                     </svg>
                  </a>
               </div>
            </div>
            <div class="my-10">
               {% if formset.non_form_errors %}
                  {% for error in formset.non_form_errors %}
                     <div class="flex items-center p-1 mb-4 text-sm text-red-800 border border-red-300 rounded-lg bg-red-50 dark:bg-gray-800 dark:text-red-400 dark:border-red-800"
                          role="alert">
                        <svg class="shrink-0 inline w-4 h-4 me-3"
                             aria-hidden="true"
                             xmlns="http://www.w3.org/2000/svg"
                             fill="currentColor"
                             viewBox="0 0 20 20">
                           <path d="M10 .5a9.5 9.5 0 1 0 9.5 9.5A9.51 9.51 0 0 0 10 .5ZM9.5 4a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3ZM12 15H8a1 1 0 0 1 0-2h1v-3H8a1 1 0 0 1 0-2h2a1 1 0 0 1 1 1v4h1a1 1 0 0 1 0 2Z" />
                        </svg>
                        <span class="sr-only">Info</span>
                        <div>
                           <span class="font-medium">An error has occured!</span> {{ error }}
                        </div>
                     </div>
                  {% endfor %}
               {% endif %}
               <h2 class="text-lg mb-2 bg-gray-100">Item Table</h2>
               <div class="overflow-x-auto">
                  <table class="w-full">
                     <thead>
                        <tr class="bg-gray-100">
                           <th class="p-2 text-left">Product</th>
                           <th class="p-2 text-left">Quantity</th>
                           <th class="p-2 text-left">Unit Price</th>
                           <th class="p-2"></th>
                        </tr>
                     </thead>
                     <tbody id="items-container">
                        {{ formset.management_form }}
                        {% for form in formset %}
                           {% include "supply_chain/po_orders/partials/item_form.html" %}
                        {% endfor %}
                     </tbody>
                  </table>
               </div>
               <div class="bg-gray-100 pl-2">
                  <button type="button"
                          class="text-blue-600 my-2"
                          hx-get="{% url 'add_item_form' %}"
                          hx-target="#items-container"
                          hx-swap="beforeend"
                          hx-trigger="click"
                          onclick="updateFormCount()">Add New Row</button>
               </div>
            </div>
            <!-- Actions -->
            <div class="mt-6 flex space-x-4">
               <button type="submit"
                       class="text-white bg-blue-500 hover:bg-blue-600 focus:ring-2 focus:ring-blue-300 font-medium rounded-lg text-sm px-5 py-2 me-2 mb-2 dark:bg-blue-600 dark:hover:bg-blue-600 focus:outline-none dark:focus:ring-blue-600">
                  Save
               </button>
               <a href="{% url 'po_order' %}"
                  class="py-2 px-4.5 me-2 mb-2 text-sm font-medium text-gray-900 focus:outline-none bg-white rounded-lg border border-gray-200 hover:bg-gray-100 hover:text-blue-700 focus:z-10 focus:ring-2 focus:ring-gray-100 dark:focus:ring-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:border-gray-600 dark:hover:text-white dark:hover:bg-gray-700">
                  Cancel
               </a>
            </div>
         </form>
      </div>
   </div>
{% endblock content %}
