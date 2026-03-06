from datetime import datetime
import os
import shutil
from typing import List, Literal
from bson import ObjectId
from fastapi import APIRouter, Body, HTTPException, Request, UploadFile, File, Form, Depends
from db.mongodb import db
from models.client import Client
from models.case import Case, HearingEntry, Note
from models.user import User

router = APIRouter()
UPLOAD_DIR = "uploads/"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---------------------------------Client-------------------------------

@router.post("/add-client")
async def add_client(user: User):
    try:
        # Validate password match
        if user.password != user.confirmPassword:
            raise HTTPException(status_code=400, detail="Passwords do not match.")

        # Check uniqueness
        existing = await db.users.find_one({"$or": [{"username": user.username}, {"email": user.email}]})
        if existing:
            raise HTTPException(status_code=400, detail="Username or Email already exists.")

        # Assign metadata
        user_dict = user.dict(exclude={"confirmPassword"}, exclude_unset=True)
        user_dict["_id"] = ObjectId()
        user_dict["createdAt"] = datetime.utcnow()
        # user_dict["createdBy"] = user.email

        # Insert into users
        await db.users.insert_one(user_dict)

        # Insert into clients using same _id
        client_dict = {
            "_id": user_dict["_id"],
            "createdAt": user_dict["createdAt"],
            # "createdBy": user_dict["createdBy"],
            "cases": []
        }

        await db.clients.insert_one(client_dict)

        return {"message": "Client added successfully", "client_id": str(user_dict["_id"])}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@router.put("/update-client/{client_id}")
async def update_client(client_id: str, updated_client: Client):
    try:
        object_id = ObjectId(client_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid client ID format.")

    # Ensure client exists
    client_in_db = await db.clients.find_one({"_id": object_id})
    if not client_in_db:
        raise HTTPException(status_code=404, detail="Client not found.")

    # Update Client collection (e.g., ModifiedAt, ModifiedBy if used)
    client_update = { 
        "modifiedAt": datetime.utcnow(),
        "modifiedBy": updated_client.user.createdBy if updated_client.user else "system",
    }

    await db.clients.update_one({"_id": object_id}, {"$set": client_update})

    # Update User if provided
    if updated_client.user:
        user_update_data = updated_client.user.dict(exclude_unset=True, exclude={"confirmPassword"})
        user_update_data["modifiedAt"] = datetime.utcnow()
        user_update_data["modifiedBy"] = updated_client.user.createdBy
        await db.users.update_one({"_id": object_id}, {"$set": user_update_data})

    return {"message": "Client and user updated successfully"}

@router.get("/clients", response_model=List[Client])
async def get_clients():
    try:
        clients = []
        async for client in db.clients.find({}):
            # Fetch user data
            user = await db.users.find_one({"_id": client["_id"]})
            if not user:
                continue

            for case in client.get("cases", []):
                case["id"] = case.get("id", "")

                # Fix caseDocuments
                for doc in case.get("caseDocuments", []):
                    if "_id" in doc:
                        doc["id"] = str(doc["_id"])
                        doc.pop("_id", None)
                    elif "id" not in doc:
                        doc["id"] = ""

                # Fix hearingHistory
                for hearing in case.get("hearingHistory", []):
                    if "hearingDate" not in hearing:
                        # If it's in a nested object like {"date": "..."}:
                        if "date" in hearing:
                            hearing["hearingDate"] = hearing["date"]
                        else:
                            hearing["hearingDate"] = ""  # or a fallback value

            client_data = {
                **client,
                "id": str(client["_id"]),
                "user": user
            }
            client_data.pop("_id", None)

            clients.append(Client(**client_data))

        return clients

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

    
@router.get("/clientById/{client_id}", response_model=Client)
async def get_client_by_id(client_id: str):
    try:
        if not ObjectId.is_valid(client_id):
            raise HTTPException(status_code=400, detail="Invalid client ID format.")

        client = await db.clients.find_one({"_id": ObjectId(client_id)})
        if not client:
            raise HTTPException(status_code=404, detail="Client not found.")

        user = await db.users.find_one({"_id": ObjectId(client_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User info for client not found.")

        # ✅ Normalize embedded cases and CaseDocuments
        for case in client.get("cases", []):
            case["id"] = case.get("id", "")  # Ensure 'id' exists

            for doc in case.get("caseDocuments", []):
                if "_id" in doc:
                    doc["id"] = str(doc["_id"])
                    doc.pop("_id", None)
                elif "id" not in doc:
                    doc["id"] = ""  # fallback to avoid validation error

        client_data = {
            **client,
            "id": str(client["_id"]),
            "user": user
        }
        client_data.pop("_id", None)

        return Client(**client_data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

# @router.delete("/delete-client/{client_id}")
# async def remove_client(client_id: str):
#     try:
#         object_id = ObjectId(client_id)

#         # Delete from client collection
#         client_res = await db.clients.delete_one({"_id": object_id})

#         # Delete from user collection
#         user_res = await db.users.delete_one({"_id": object_id})

#         if client_res.deleted_count or user_res.deleted_count:
#             return {"status": "Success", "message": "Client and User Removed"}

#         raise HTTPException(status_code=404, detail="Client not found")

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")

@router.put("/client-status/{client_id}/status")
async def update_client_status(client_id: str, is_active: Literal[True, False] = Body(...)):
    try:
        obj_id = ObjectId(client_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid client ID")

    result = await db.users.update_one(
        {"_id": obj_id},
        {"$set": {"isActive": is_active}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Client not found or status unchanged")

    return {"message": "Status updated", "isActive": is_active}
# ---------------------------------Case-------------------------------

@router.post("/add-case")
async def add_case(case: Case):
    case_dict = case.dict(by_alias=True)
    case_dict["_id"] = ObjectId()
    await db.cases.insert_one(case_dict)

    embedded_case = case_dict.copy()
    embedded_case["id"] = str(case_dict["_id"])
    embedded_case.pop("_id", None)

    result = await db.clients.update_one(
        {"_id": ObjectId(case.clientId)},
        {"$push": {"cases": embedded_case}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Client not found or case not added to client")

    return {"message": "Case created", "case_id": str(case_dict["_id"])}

@router.put("/update-case/{case_id}")
async def update_case(case_id: str, case: Case):
    try:
        existing_case = await db.cases.find_one({"_id": ObjectId(case_id)})
        if not existing_case:
            raise HTTPException(status_code=404, detail="Case not found")

        new_docs = []
        existing_doc_signatures = set(
            (doc["fileName"], doc["type"]) for doc in existing_case.get("caseDocuments", [])
        )

        for doc in case.caseDocuments or []:
            if (doc.fileName, doc.type) not in existing_doc_signatures:
                doc_dict = doc.dict(exclude_unset=True)
                doc_dict["caseId"] = case_id
                doc_dict["createdAt"] = doc_dict.get("createdAt") or datetime.utcnow()
                doc_dict["modifiedAt"] = datetime.utcnow()
                result = await db.casedocuments.insert_one(doc_dict)
                doc_dict["id"] = str(result.inserted_id)
                doc_dict.pop("_id", None)
                new_docs.append({"url": doc_dict["url"], "fileName": doc_dict["fileName"], "type": doc_dict["type"]})

        case_dict = case.dict(exclude_unset=True, by_alias=True)
        case_dict.pop("caseDocuments", None)

        await db.cases.update_one(
            {"_id": ObjectId(case_id)},
            {"$set": case_dict}
        )

        if new_docs:
            await db.cases.update_one(
                {"_id": ObjectId(case_id)},
                {"$push": {"caseDocuments": {"$each": new_docs}}, "$set": {"modifiedAt": datetime.utcnow()}}
            )

        updated_case = await db.cases.find_one({"_id": ObjectId(case_id)})
        case_docs = updated_case.get("caseDocuments", [])
        for doc in case_docs:
            if "_id" in doc:
                doc["id"] = str(doc["_id"])
                doc.pop("_id", None)

        embedded_case = {**updated_case, "id": str(updated_case["_id"])}
        embedded_case.pop("_id", None)

        await db.clients.update_one(
            {"_id": ObjectId(case.clientId), "cases.id": case_id},
            {"$set": {"cases.$": embedded_case}}
        )

        return {"status": "Success", "message": "Case Updated"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cases", response_model=List[Case])
async def list_cases():
    cases = []
    try:
        async for doc in db.cases.find():
            doc["id"] = str(doc["_id"])
            doc.pop("_id", None)

            # Ensure each embedded caseDocument follows the expected model
            if "caseDocuments" in doc:
                for embedded_doc in doc["caseDocuments"]:
                    # Clean up individual document if needed
                    embedded_doc.pop("_id", None)  # remove any unexpected field
                    embedded_doc.setdefault("createdAt", datetime.utcnow())

            cases.append(Case(**doc))
        return cases

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch cases: {str(e)}")

@router.get("/caseById/{case_id}", response_model=Case)
async def get_case(case_id: str):
    try:
        case = await db.cases.find_one({"_id": ObjectId(case_id)})
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        case["id"] = str(case["_id"])
        case.pop("_id", None)

        if "caseDocuments" in case:
            for embedded_doc in case["caseDocuments"]:
                embedded_doc.pop("_id", None)
                embedded_doc.setdefault("createdAt", datetime.utcnow())

        return Case(**case)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch case: {str(e)}")

@router.delete("/delete-case/{case_id}")  
async def remove_case(case_id: str):
    case = await db.cases.find_one({"_id": ObjectId(case_id)})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    # Delete from cases collection
    await db.cases.delete_one({"_id": ObjectId(case_id)})
    # Pull from client.cases array
    await db.clients.update_one(
        {"_id": ObjectId(case["clientId"])},
        {"$pull": {"cases": {"id": case_id}}}
    )

    return {"status": "Success", "message": "Case Removed"}

# ------------------------Case Document-------------------------------

@router.put("/cases/{case_id}/add-document")
async def add_case_document(case_id: str, file: UploadFile = File(...)):
    try:
        # Check if case exists
        case = await db.cases.find_one({"_id": ObjectId(case_id)})
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        # Save file
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        file_name = f"{timestamp}_{file.filename}"
        file_path = os.path.join(UPLOAD_DIR, file_name)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        file_url = f"/{UPLOAD_DIR}{file_name}"
        file_type = file.content_type

        # Prepare document object
        doc_entry = {
            "url": file_url,
            "fileName": file.filename,
            "type": file_type,
            "createdAt": datetime.utcnow()
        }

        # Update the case: push new document
        await db.cases.update_one(
            {"_id": ObjectId(case_id)},
            {
                "$push": {"caseDocuments": doc_entry},
                "$set": {"modifiedAt": datetime.utcnow()}
            }
        )

        # Update embedded case in client
        updated_case = await db.cases.find_one({"_id": ObjectId(case_id)})
        updated_case["id"] = str(updated_case["_id"])
        updated_case.pop("_id", None)

        await db.clients.update_one(
            {"_id": ObjectId(updated_case.get("clientId")), "cases.id": case_id},
            {"$set": {"cases.$": updated_case}}
        )

        return {"message": "Document added successfully."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add document: {str(e)}")


# -------------------------Update Hearing-------------------------------

@router.put("/cases/{case_id}/update-hearing")
async def update_hearing(case_id: str, data: HearingEntry):
    try:
        case = await db.cases.find_one({"_id": ObjectId(case_id)})
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        # 1. Update next hearing date if provided
        update_fields = {}
        if data.hearingDate:
            update_fields["hearingDate"] = data.hearingDate

        # 2. Prepare note
        hearing_note = data.note.strip() if data.note else "Hearing is updated."

        hearing_entry = {
            "hearingDate": data.hearingDate or case.get("hearingDate"),
            "note": hearing_note,
            "updatedBy": case.get("createdBy"),
            "createdAt": datetime.utcnow()
        }

        # 3. Apply updates
        await db.cases.update_one(
            {"_id": ObjectId(case_id)},
            {
                "$set": {
                    **update_fields,
                    "modifiedAt": datetime.utcnow()
                },
                "$push": {"hearingHistory": hearing_entry}
            }
        )

        # 4. Update embedded case in clients collection
        updated_case = await db.cases.find_one({"_id": ObjectId(case_id)})
        updated_case["id"] = str(updated_case["_id"])
        updated_case.pop("_id", None)

        await db.clients.update_one(
            {"_id": ObjectId(updated_case.get("clientId") or updated_case.get("clientId")), "cases.id": case_id},
            {"$set": {"cases.$": updated_case}}
        )

        return {"message": "Hearing updated successfully."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")

# -------------------------Case Notes-------------------------------

@router.put("/cases/{case_id}/add-note")
async def add_case_note(case_id: str, note_data: Note):
    try:
        case = await db.cases.find_one({"_id": ObjectId(case_id)})
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        note_entry = {
            "description": note_data.description,
            "createdAt": note_data.createdAt or datetime.utcnow()
        }

        # Update the notes array and modifiedAt
        await db.cases.update_one(
            {"_id": ObjectId(case_id)},
            {
                "$push": {"notes": note_entry},
                "$set": {"modifiedAt": datetime.utcnow()}
            }
        )

        # Update embedded case in clients collection
        updated_case = await db.cases.find_one({"_id": ObjectId(case_id)})
        updated_case["id"] = str(updated_case["_id"])
        updated_case.pop("_id", None)

        await db.clients.update_one(
            {"_id": ObjectId(updated_case.get("clientId")), "cases.id": case_id},
            {"$set": {"cases.$": updated_case}}
        )

        return {"message": "Note added successfully."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add note: {str(e)}")
