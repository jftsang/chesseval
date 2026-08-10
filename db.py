import os
from typing import Annotated, Any, Generator

import dotenv
from fastapi import Depends
from sqlmodel import Session, create_engine

dotenv.load_dotenv()

DATABASE = os.getenv("DATABASE")
connect_args = {
    # "check_same_thread": False
}
engine = create_engine(DATABASE, connect_args=connect_args)


def get_session() -> Generator[Session, Any, None]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
