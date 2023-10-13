Due to the fact that the original development platform (Termux) could not install the langchain toolkit (due to numpy), and in order to facilitate the use of GPTUI by other Termux users, part of the langchain source code that is needed has been copied into this project to use some of the functions of langchain. Thanks to the hard work of the langchain developers. If the installation problem of langchain is solved later, the langchain toolkit will be installed directly.

Langchain tools that have already been integrated:
- TextLoader
- UnstructuredHTMLLoader
- BSHTMLLoader

Required dependencies:
- pydantic
