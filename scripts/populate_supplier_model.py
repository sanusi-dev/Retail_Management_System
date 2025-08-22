from supply_chain.models import *
from account.models import CustomUser
from faker import Faker

faker = Faker()


# def populate_supplier_model():
#     try:
#         user = CustomUser.objects.first()
#         if not user:
#             print("You must create a user first")
#             return
#     except CustomUser.DoesNotExist:
#         print("The model CustomUser does not exist in the database")
#         return

#     suppliers = []
#     for i in range(20):
#         supplier = Supplier(
#             name=faker.company(),
#             phone=faker.phone_number(),
#             email=faker.email(),
#             address=faker.address(),
#             created_by=user,
#             updated_by=user,
#         )
#         suppliers.append(supplier)

#     Supplier.objects.bulk_create(suppliers)
#     print("Suppliers succesfully created")


def run():
    suppliers = Supplier.objects.all()
    fields = [
        "firstname",
        "lastname",
        "company_name",
        "display_name",
        "work_phone",
    ]

    for supplier in suppliers:
        supplier.firstname = faker.first_name()
        supplier.lastname = faker.last_name()
        supplier.company_name = faker.company()
        supplier.display_name = faker.name()
        supplier.work_phone = faker.phone_number()

    Supplier.objects.bulk_update(suppliers, fields)
    print("Successfully updated")
