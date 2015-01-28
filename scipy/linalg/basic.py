#
# Author: Pearu Peterson, March 2002
#
# w/ additions by Travis Oliphant, March 2002
#              and Jake Vanderplas, August 2012

from __future__ import division, print_function, absolute_import

__all__ = ['solve', 'solve_triangular', 'solveh_banded', 'solve_banded',
           'solve_toeplitz', 'inv', 'det', 'lstsq', 'pinv', 'pinv2', 'pinvh']

import numpy as np

from .flinalg import get_flinalg_funcs
from .lapack import get_lapack_funcs
from .misc import LinAlgError, _datacopied
from .decomp import _asarray_validated
from . import decomp, decomp_svd
from ._solve_toeplitz import levinson


# Linear equations
def solve(a, b, sym_pos=False, lower=False, overwrite_a=False,
          overwrite_b=False, debug=False, check_finite=True):
    """
    Solve the equation ``a x = b`` for ``x``.

    Parameters
    ----------
    a : (M, M) array_like
        A square matrix.
    b : (M,) or (M, N) array_like
        Right-hand side matrix in ``a x = b``.
    sym_pos : bool
        Assume `a` is symmetric and positive definite.
    lower : boolean
        Use only data contained in the lower triangle of `a`, if `sym_pos` is
        true.  Default is to use upper triangle.
    overwrite_a : bool
        Allow overwriting data in `a` (may enhance performance).
        Default is False.
    overwrite_b : bool
        Allow overwriting data in `b` (may enhance performance).
        Default is False.
    check_finite : boolean, optional
        Whether to check that the input matrices contain only finite numbers.
        Disabling may give a performance gain, but may result in problems
        (crashes, non-termination) if the inputs do contain infinities or NaNs.

    Returns
    -------
    x : (M,) or (M, N) ndarray
        Solution to the system ``a x = b``.  Shape of the return matches the
        shape of `b`.

    Raises
    ------
    LinAlgError
        If `a` is singular.

    Examples
    --------
    Given `a` and `b`, solve for `x`:

    >>> a = np.array([[3,2,0],[1,-1,0],[0,5,1]])
    >>> b = np.array([2,4,-1])
    >>> x = linalg.solve(a,b)
    >>> x
    array([ 2., -2.,  9.])
    >>> np.dot(a, x) == b
    array([ True,  True,  True], dtype=bool)

    """
    a1 = _asarray_validated(a, check_finite=check_finite)
    b1 = _asarray_validated(b, check_finite=check_finite)
    if len(a1.shape) != 2 or a1.shape[0] != a1.shape[1]:
        raise ValueError('expected square matrix')
    if a1.shape[0] != b1.shape[0]:
        raise ValueError('incompatible dimensions')
    overwrite_a = overwrite_a or _datacopied(a1, a)
    overwrite_b = overwrite_b or _datacopied(b1, b)
    if debug:
        print('solve:overwrite_a=',overwrite_a)
        print('solve:overwrite_b=',overwrite_b)
    if sym_pos:
        posv, = get_lapack_funcs(('posv',), (a1,b1))
        c, x, info = posv(a1, b1, lower=lower,
                        overwrite_a=overwrite_a,
                        overwrite_b=overwrite_b)
    else:
        gesv, = get_lapack_funcs(('gesv',), (a1,b1))
        lu, piv, x, info = gesv(a1, b1, overwrite_a=overwrite_a,
                                            overwrite_b=overwrite_b)

    if info == 0:
        return x
    if info > 0:
        raise LinAlgError("singular matrix")
    raise ValueError('illegal value in %d-th argument of internal gesv|posv'
                                                                    % -info)


def solve_triangular(a, b, trans=0, lower=False, unit_diagonal=False,
                     overwrite_b=False, debug=False, check_finite=True):
    """
    Solve the equation `a x = b` for `x`, assuming a is a triangular matrix.

    Parameters
    ----------
    a : (M, M) array_like
        A triangular matrix
    b : (M,) or (M, N) array_like
        Right-hand side matrix in `a x = b`
    lower : boolean
        Use only data contained in the lower triangle of `a`.
        Default is to use upper triangle.
    trans : {0, 1, 2, 'N', 'T', 'C'}, optional
        Type of system to solve:

        ========  =========
        trans     system
        ========  =========
        0 or 'N'  a x  = b
        1 or 'T'  a^T x = b
        2 or 'C'  a^H x = b
        ========  =========
    unit_diagonal : bool, optional
        If True, diagonal elements of `a` are assumed to be 1 and
        will not be referenced.
    overwrite_b : bool, optional
        Allow overwriting data in `b` (may enhance performance)
    check_finite : bool, optional
        Whether to check that the input matrices contain only finite numbers.
        Disabling may give a performance gain, but may result in problems
        (crashes, non-termination) if the inputs do contain infinities or NaNs.

    Returns
    -------
    x : (M,) or (M, N) ndarray
        Solution to the system `a x = b`.  Shape of return matches `b`.

    Raises
    ------
    LinAlgError
        If `a` is singular

    Notes
    -----
    .. versionadded:: 0.9.0

    """
    a1 = _asarray_validated(a, check_finite=check_finite)
    b1 = _asarray_validated(b, check_finite=check_finite)
    if len(a1.shape) != 2 or a1.shape[0] != a1.shape[1]:
        raise ValueError('expected square matrix')
    if a1.shape[0] != b1.shape[0]:
        raise ValueError('incompatible dimensions')
    overwrite_b = overwrite_b or _datacopied(b1, b)
    if debug:
        print('solve:overwrite_b=',overwrite_b)
    trans = {'N': 0, 'T': 1, 'C': 2}.get(trans, trans)
    trtrs, = get_lapack_funcs(('trtrs',), (a1,b1))
    x, info = trtrs(a1, b1, overwrite_b=overwrite_b, lower=lower,
                    trans=trans, unitdiag=unit_diagonal)

    if info == 0:
        return x
    if info > 0:
        raise LinAlgError("singular matrix: resolution failed at diagonal %s" % (info-1))
    raise ValueError('illegal value in %d-th argument of internal trtrs'
            % -info)


def solve_banded(l_and_u, ab, b, overwrite_ab=False, overwrite_b=False,
                debug=False, check_finite=True):
    """
    Solve the equation a x = b for x, assuming a is banded matrix.

    The matrix a is stored in `ab` using the matrix diagonal ordered form::

        ab[u + i - j, j] == a[i,j]

    Example of `ab` (shape of a is (6,6), `u` =1, `l` =2)::

        *    a01  a12  a23  a34  a45
        a00  a11  a22  a33  a44  a55
        a10  a21  a32  a43  a54   *
        a20  a31  a42  a53   *    *

    Parameters
    ----------
    (l, u) : (integer, integer)
        Number of non-zero lower and upper diagonals
    ab : (`l` + `u` + 1, M) array_like
        Banded matrix
    b : (M,) or (M, K) array_like
        Right-hand side
    overwrite_ab : boolean, optional
        Discard data in `ab` (may enhance performance)
    overwrite_b : boolean, optional
        Discard data in `b` (may enhance performance)
    check_finite : boolean, optional
        Whether to check that the input matrices contain only finite numbers.
        Disabling may give a performance gain, but may result in problems
        (crashes, non-termination) if the inputs do contain infinities or NaNs.

    Returns
    -------
    x : (M,) or (M, K) ndarray
        The solution to the system a x = b.  Returned shape depends on the
        shape of `b`.

    """
    a1 = _asarray_validated(ab, check_finite=check_finite)
    b1 = _asarray_validated(b, check_finite=check_finite)
    # Validate shapes.
    if a1.shape[-1] != b1.shape[0]:
        raise ValueError("shapes of ab and b are not compatible.")
    (l, u) = l_and_u
    if l + u + 1 != a1.shape[0]:
        raise ValueError("invalid values for the number of lower and upper diagonals:"
                " l+u+1 (%d) does not equal ab.shape[0] (%d)" % (l+u+1, ab.shape[0]))

    overwrite_b = overwrite_b or _datacopied(b1, b)
    if l == u == 1:
        overwrite_ab = overwrite_ab or _datacopied(b1, b)
        gtsv, = get_lapack_funcs(('gtsv',), (a1, b1))
        du = a1[0,1:]
        d = a1[1,:]
        dl = a1[2,:-1]
        du2, d, du, x, info = gtsv(dl, d, du, b, overwrite_ab, overwrite_ab,
                                   overwrite_ab, overwrite_b)
    else:
        gbsv, = get_lapack_funcs(('gbsv',), (a1, b1))
        a2 = np.zeros((2*l+u+1, a1.shape[1]), dtype=gbsv.dtype)
        a2[l:,:] = a1
        lu, piv, x, info = gbsv(l, u, a2, b1, overwrite_ab=True,
                                                    overwrite_b=overwrite_b)
    if info == 0:
        return x
    if info > 0:
        raise LinAlgError("singular matrix")
    raise ValueError('illegal value in %d-th argument of internal gbsv/gtsv' % -info)


def solveh_banded(ab, b, overwrite_ab=False, overwrite_b=False, lower=False,
                    check_finite=True):
    """
    Solve equation a x = b. a is Hermitian positive-definite banded matrix.

    The matrix a is stored in `ab` either in lower diagonal or upper
    diagonal ordered form:

        ab[u + i - j, j] == a[i,j]        (if upper form; i <= j)
        ab[    i - j, j] == a[i,j]        (if lower form; i >= j)

    Example of `ab` (shape of a is (6,6), `u` =2)::

        upper form:
        *   *   a02 a13 a24 a35
        *   a01 a12 a23 a34 a45
        a00 a11 a22 a33 a44 a55

        lower form:
        a00 a11 a22 a33 a44 a55
        a10 a21 a32 a43 a54 *
        a20 a31 a42 a53 *   *

    Cells marked with * are not used.

    Parameters
    ----------
    ab : (`u` + 1, M) array_like
        Banded matrix
    b : (M,) or (M, K) array_like
        Right-hand side
    overwrite_ab : bool, optional
        Discard data in `ab` (may enhance performance)
    overwrite_b : bool, optional
        Discard data in `b` (may enhance performance)
    lower : bool, optional
        Is the matrix in the lower form. (Default is upper form)
    check_finite : boolean, optional
        Whether to check that the input matrices contain only finite numbers.
        Disabling may give a performance gain, but may result in problems
        (crashes, non-termination) if the inputs do contain infinities or NaNs.

    Returns
    -------
    x : (M,) or (M, K) ndarray
        The solution to the system a x = b.  Shape of return matches shape
        of `b`.

    """
    a1 = _asarray_validated(ab, check_finite=check_finite)
    b1 = _asarray_validated(b, check_finite=check_finite)
    # Validate shapes.
    if a1.shape[-1] != b1.shape[0]:
        raise ValueError("shapes of ab and b are not compatible.")

    overwrite_b = overwrite_b or _datacopied(b1, b)
    overwrite_ab = overwrite_ab or _datacopied(a1, ab)
    
    if a1.shape[0] == 2:
        ptsv, = get_lapack_funcs(('ptsv',), (a1, b1))
        if lower:
            d = a1[0,:].real
            e = a1[1,:-1]
        else:
            d = a1[1,:].real
            e = a1[0,1:].conj()
        d, du, x, info = ptsv(d, e, b1, overwrite_ab, overwrite_ab, overwrite_b)
    else:
        pbsv, = get_lapack_funcs(('pbsv',), (a1, b1))
        c, x, info = pbsv(a1, b1, lower=lower, overwrite_ab=overwrite_ab,
                                                overwrite_b=overwrite_b)
    if info > 0:
        raise LinAlgError("%d-th leading minor not positive definite" % info)
    if info < 0:
        raise ValueError('illegal value in %d-th argument of internal pbsv'
                                                                    % -info)
    return x


def solve_toeplitz(c_or_cr, b, check_finite=True):
    """Solve a Toeplitz system using Levinson Recursion

    The Toeplitz matrix has constant diagonals, with c as its first column
    and r as its first row.  If r is not given, ``r == conjugate(c)`` is
    assumed.

    Parameters
    ----------
    c_or_cr : array_like or tuple of (array_like, array_like)
        The vector ``c``, or a tuple of arrays (``c``, ``r``). Whatever the
        actual shape of ``c``, it will be converted to a 1-D array. If not
        supplied, ``r = conjugate(c)`` is assumed; in this case, if c[0] is
        real, the Toeplitz matrix is Hermitian. r[0] is ignored; the first row
        of the Toeplitz matrix is ``[c[0], r[1:]]``.  Whatever the actual shape
        of ``r``, it will be converted to a 1-D array.
    b : (M,) or (M, K) array_like
        Right-hand side in ``T x = b``.
    check_finite : boolean, optional
        Whether to check that the input matrices contain only finite numbers.
        Disabling may give a performance gain, but may result in problems
        (result entirely NaNs) if the inputs do contain infinities or NaNs.

    Returns
    -------
    x : (M,) or (M, K) ndarray
        The solution to the system ``T x = b``.  Shape of return matches shape
        of `b`.

    Notes
    -----
    The solution is computed using Levinson-Durbin recursion, which is faster
    than generic least-squares methods, but can be less numerically stable.
    """
    # If numerical stability of this algorithim is a problem, a future
    # developer might consider implementing other O(N^2) Toeplitz solvers,
    # such as GKO (http://www.jstor.org/stable/2153371) or Bareiss.
    if isinstance(c_or_cr, tuple):
        c, r = c_or_cr
        c = _asarray_validated(c, check_finite=check_finite).ravel()
        r = _asarray_validated(r, check_finite=check_finite).ravel()
    else:
        c = _asarray_validated(c_or_cr, check_finite=check_finite).ravel()
        r = c.conjugate()

    # Form a 1D array of values to be used in the matrix, containing a reversed
    # copy of r[1:], followed by c.
    vals = np.concatenate((r[-1:0:-1], c))
    if b is None:
        raise ValueError('illegal value, `b` is a required argument')
    if vals.shape[0] != (2*b.shape[0] - 1):
        raise ValueError('incompatible dimensions')

    b = _asarray_validated(b)
    if np.iscomplexobj(vals) or np.iscomplexobj(b):
        vals = np.asarray(vals, dtype=np.complex128, order='c')
        b = np.asarray(b, dtype=np.complex128)

    else:
        vals = np.asarray(vals, dtype=np.double, order='c')
        b = np.asarray(b, dtype=np.double)

    if b.ndim == 1:
        x, _ = levinson(vals, np.ascontiguousarray(b))
    else:
        b_shape = b.shape
        b = b.reshape(b.shape[0], -1)
        x = np.column_stack(
            (levinson(vals, np.ascontiguousarray(b[:,i]))[0])
            for i in range(b.shape[1]))
        x = x.reshape(*b_shape)

    return x


# matrix inversion
def inv(a, overwrite_a=False, check_finite=True):
    """
    Compute the inverse of a matrix.

    Parameters
    ----------
    a : array_like
        Square matrix to be inverted.
    overwrite_a : bool, optional
        Discard data in `a` (may improve performance). Default is False.
    check_finite : boolean, optional
        Whether to check that the input matrix contains only finite numbers.
        Disabling may give a performance gain, but may result in problems
        (crashes, non-termination) if the inputs do contain infinities or NaNs.

    Returns
    -------
    ainv : ndarray
        Inverse of the matrix `a`.

    Raises
    ------
    LinAlgError :
        If `a` is singular.
    ValueError :
        If `a` is not square, or not 2-dimensional.

    Examples
    --------
    >>> a = np.array([[1., 2.], [3., 4.]])
    >>> sp.linalg.inv(a)
    array([[-2. ,  1. ],
           [ 1.5, -0.5]])
    >>> np.dot(a, sp.linalg.inv(a))
    array([[ 1.,  0.],
           [ 0.,  1.]])

    """
    a1 = _asarray_validated(a, check_finite=check_finite)
    if len(a1.shape) != 2 or a1.shape[0] != a1.shape[1]:
        raise ValueError('expected square matrix')
    overwrite_a = overwrite_a or _datacopied(a1, a)
    #XXX: I found no advantage or disadvantage of using finv.
##     finv, = get_flinalg_funcs(('inv',),(a1,))
##     if finv is not None:
##         a_inv,info = finv(a1,overwrite_a=overwrite_a)
##         if info==0:
##             return a_inv
##         if info>0: raise LinAlgError, "singular matrix"
##         if info<0: raise ValueError,\
##            'illegal value in %d-th argument of internal inv.getrf|getri'%(-info)
    getrf, getri, getri_lwork = get_lapack_funcs(('getrf','getri', 'getri_lwork'), (a1,))
    lu, piv, info = getrf(a1, overwrite_a=overwrite_a)
    if info == 0:
        lwork, info = getri_lwork(a1.shape[0])
        if info != 0:
            raise ValueError('internal getri work space query failed: %d' % (info,))
        lwork = int(lwork.real)

        # XXX: the following line fixes curious SEGFAULT when
        # benchmarking 500x500 matrix inverse. This seems to
        # be a bug in LAPACK ?getri routine because if lwork is
        # minimal (when using lwork[0] instead of lwork[1]) then
        # all tests pass. Further investigation is required if
        # more such SEGFAULTs occur.
        lwork = int(1.01 * lwork)
        inv_a, info = getri(lu, piv, lwork=lwork, overwrite_lu=1)
    if info > 0:
        raise LinAlgError("singular matrix")
    if info < 0:
        raise ValueError('illegal value in %d-th argument of internal '
                                                    'getrf|getri' % -info)
    return inv_a


### Determinant

def det(a, overwrite_a=False, check_finite=True):
    """
    Compute the determinant of a matrix

    The determinant of a square matrix is a value derived arithmetically
    from the coefficients of the matrix.

    The determinant for a 3x3 matrix, for example, is computed as follows::

        a    b    c
        d    e    f = A
        g    h    i

        det(A) = a*e*i + b*f*g + c*d*h - c*e*g - b*d*i - a*f*h

    Parameters
    ----------
    a : (M, M) array_like
        A square matrix.
    overwrite_a : bool
        Allow overwriting data in a (may enhance performance).
    check_finite : boolean, optional
        Whether to check that the input matrix contains only finite numbers.
        Disabling may give a performance gain, but may result in problems
        (crashes, non-termination) if the inputs do contain infinities or NaNs.

    Returns
    -------
    det : float or complex
        Determinant of `a`.

    Notes
    -----
    The determinant is computed via LU factorization, LAPACK routine z/dgetrf.

    Examples
    --------
    >>> a = np.array([[1,2,3],[4,5,6],[7,8,9]])
    >>> linalg.det(a)
    0.0
    >>> a = np.array([[0,2,3],[4,5,6],[7,8,9]])
    >>> linalg.det(a)
    3.0

    """
    a1 = _asarray_validated(a, check_finite=check_finite)
    if len(a1.shape) != 2 or a1.shape[0] != a1.shape[1]:
        raise ValueError('expected square matrix')
    overwrite_a = overwrite_a or _datacopied(a1, a)
    fdet, = get_flinalg_funcs(('det',), (a1,))
    a_det, info = fdet(a1, overwrite_a=overwrite_a)
    if info < 0:
        raise ValueError('illegal value in %d-th argument of internal '
                                                        'det.getrf' % -info)
    return a_det

### Linear Least Squares


def lstsq(a, b, cond=None, overwrite_a=False, overwrite_b=False,
          check_finite=True, lapack_driver = 'gelsd'):
    """
    Compute least-squares solution to equation Ax = b.

    Compute a vector x such that the 2-norm ``|b - A x|`` is minimized.

    Parameters
    ----------
    a : (M, N) array_like
        Left hand side matrix (2-D array).
    b : (M,) or (M, K) array_like
        Right hand side matrix or vector (1-D or 2-D array).
    cond : float, optional
        Cutoff for 'small' singular values; used to determine effective
        rank of a. Singular values smaller than
        ``rcond * largest_singular_value`` are considered zero.
    overwrite_a : bool, optional
        Discard data in `a` (may enhance performance). Default is False.
    overwrite_b : bool, optional
        Discard data in `b` (may enhance performance). Default is False.
    check_finite : boolean, optional
        Whether to check that the input matrices contain only finite numbers.
        Disabling may give a performance gain, but may result in problems
        (crashes, non-termination) if the inputs do contain infinities or NaNs.
    lapack_driver: string, optional
        Options are 'gelsd', 'gelsy', 'gelss'. Which LAPACK driver used to 
        solve the least-squares problem. Default is goog choise. However 
        'gelsy' can work slightly faster on many problems. 'gelss' was used
        used historically. It is generally slow but uses less memory.
    Returns
    -------
    x : (N,) or (N, K) ndarray
        Least-squares solution.  Return shape matches shape of `b`.
    residues : () or (1,) or (K,) ndarray
        Sums of residues, squared 2-norm for each column in ``b - a x``.
        If rank of matrix a is < N or > M this is an empty array.
        If b was 1-D, this is an (1,) shape array, otherwise the shape is (K,).
    rank : int
        Effective rank of matrix `a`.
    s : (min(M,N),) ndarray
        Singular values of `a`. The condition number of a is
        ``abs(s[0]/s[-1])``.

    Raises
    ------
    LinAlgError :
        If computation does not converge.


    See Also
    --------
    optimize.nnls : linear least squares with non-negativity constraint

    """
    a1 = _asarray_validated(a, check_finite=check_finite)
    b1 = _asarray_validated(b, check_finite=check_finite)
    if len(a1.shape) != 2:
        raise ValueError('expected matrix')
    m, n = a1.shape
    if len(b1.shape) == 2:
        nrhs = b1.shape[1]
    else:
        nrhs = 1
    if m != b1.shape[0]:
        raise ValueError('incompatible dimensions')
    if not lapack_driver in ('gelsd','gelsy','gelss'):
        raise ValueError('LAPACK driver "%s"is not found' % lapack_driver)
    lapack_func, = get_lapack_funcs((lapack_driver,), (a1, b1))
    if n > m:
        # need to extend b matrix as it will be filled with
        # a larger solution matrix
        if len(b1.shape) == 2:
            b2 = np.zeros((n, nrhs), dtype=lapack_func.dtype)
            b2[:m,:] = b1
        else:
            b2 = np.zeros(n, dtype=lapack_func.dtype)
            b2[:m] = b1
        b1 = b2

    overwrite_a = overwrite_a or _datacopied(a1, a)
    overwrite_b = overwrite_b or _datacopied(b1, b)

    if lapack_driver == 'gelss':
        # get optimal work array
        work = lapack_func(a1, b1, lwork=-1)[4]
        lwork = work[0].real.astype(np.int)
        v, x, s, rank, work, info = lapack_func(
            a1, b1, cond=cond, lwork=lwork, overwrite_a=overwrite_a,
            overwrite_b=overwrite_b)

        if info > 0:
            raise LinAlgError("SVD did not converge in Linear Least Squares")
        if info < 0:
            raise ValueError('illegal value in %d-th argument of internal gelss'
                                                                        % -info)
        resids = np.asarray([], dtype=x.dtype)
        if n < m:
            x1 = x[:n]
            if rank == n:
                resids = np.sum(np.abs(x[n:])**2, axis=0)
            x = x1
    return x, resids, rank, s


def pinv(a, cond=None, rcond=None, return_rank=False, check_finite=True):
    """
    Compute the (Moore-Penrose) pseudo-inverse of a matrix.

    Calculate a generalized inverse of a matrix using a least-squares
    solver.

    Parameters
    ----------
    a : (M, N) array_like
        Matrix to be pseudo-inverted.
    cond, rcond : float, optional
        Cutoff for 'small' singular values in the least-squares solver.
        Singular values smaller than ``rcond * largest_singular_value``
        are considered zero.
    return_rank : bool, optional
        if True, return the effective rank of the matrix
    check_finite : boolean, optional
        Whether to check that the input matrix contains only finite numbers.
        Disabling may give a performance gain, but may result in problems
        (crashes, non-termination) if the inputs do contain infinities or NaNs.

    Returns
    -------
    B : (N, M) ndarray
        The pseudo-inverse of matrix `a`.
    rank : int
        The effective rank of the matrix.  Returned if return_rank == True

    Raises
    ------
    LinAlgError
        If computation does not converge.

    Examples
    --------
    >>> a = np.random.randn(9, 6)
    >>> B = linalg.pinv(a)
    >>> np.allclose(a, dot(a, dot(B, a)))
    True
    >>> np.allclose(B, dot(B, dot(a, B)))
    True

    """
    a = _asarray_validated(a, check_finite=check_finite)
    b = np.identity(a.shape[0], dtype=a.dtype)
    if rcond is not None:
        cond = rcond

    x, resids, rank, s = lstsq(a, b, cond=cond, check_finite=False)

    if return_rank:
        return x, rank
    else:
        return x


def pinv2(a, cond=None, rcond=None, return_rank=False, check_finite=True):
    """
    Compute the (Moore-Penrose) pseudo-inverse of a matrix.

    Calculate a generalized inverse of a matrix using its
    singular-value decomposition and including all 'large' singular
    values.

    Parameters
    ----------
    a : (M, N) array_like
        Matrix to be pseudo-inverted.
    cond, rcond : float or None
        Cutoff for 'small' singular values.
        Singular values smaller than ``rcond*largest_singular_value``
        are considered zero.
        If None or -1, suitable machine precision is used.
    return_rank : bool, optional
        if True, return the effective rank of the matrix
    check_finite : boolean, optional
        Whether to check that the input matrix contains only finite numbers.
        Disabling may give a performance gain, but may result in problems
        (crashes, non-termination) if the inputs do contain infinities or NaNs.

    Returns
    -------
    B : (N, M) ndarray
        The pseudo-inverse of matrix `a`.
    rank : int
        The effective rank of the matrix.  Returned if return_rank == True

    Raises
    ------
    LinAlgError
        If SVD computation does not converge.

    Examples
    --------
    >>> a = np.random.randn(9, 6)
    >>> B = linalg.pinv2(a)
    >>> np.allclose(a, dot(a, dot(B, a)))
    True
    >>> np.allclose(B, dot(B, dot(a, B)))
    True

    """
    a = _asarray_validated(a, check_finite=check_finite)
    u, s, vh = decomp_svd.svd(a, full_matrices=False, check_finite=False)

    if rcond is not None:
        cond = rcond
    if cond in [None,-1]:
        t = u.dtype.char.lower()
        factor = {'f': 1E3, 'd': 1E6}
        cond = factor[t] * np.finfo(t).eps

    rank = np.sum(s > cond * np.max(s))
    psigma_diag = 1.0 / s[: rank]

    B = np.transpose(np.conjugate(np.dot(u[:, : rank] *
                                         psigma_diag, vh[: rank])))

    if return_rank:
        return B, rank
    else:
        return B


def pinvh(a, cond=None, rcond=None, lower=True, return_rank=False,
          check_finite=True):
    """
    Compute the (Moore-Penrose) pseudo-inverse of a Hermitian matrix.

    Calculate a generalized inverse of a Hermitian or real symmetric matrix
    using its eigenvalue decomposition and including all eigenvalues with
    'large' absolute value.

    Parameters
    ----------
    a : (N, N) array_like
        Real symmetric or complex hermetian matrix to be pseudo-inverted
    cond, rcond : float or None
        Cutoff for 'small' eigenvalues.
        Singular values smaller than rcond * largest_eigenvalue are considered
        zero.

        If None or -1, suitable machine precision is used.
    lower : bool
        Whether the pertinent array data is taken from the lower or upper
        triangle of a. (Default: lower)
    return_rank : bool, optional
        if True, return the effective rank of the matrix
    check_finite : boolean, optional
        Whether to check that the input matrix contains only finite numbers.
        Disabling may give a performance gain, but may result in problems
        (crashes, non-termination) if the inputs do contain infinities or NaNs.

    Returns
    -------
    B : (N, N) ndarray
        The pseudo-inverse of matrix `a`.
    rank : int
        The effective rank of the matrix.  Returned if return_rank == True

    Raises
    ------
    LinAlgError
        If eigenvalue does not converge

    Examples
    --------
    >>> import numpy as np
    >>> a = np.random.randn(9, 6)
    >>> a = np.dot(a, a.T)
    >>> B = pinvh(a)
    >>> np.allclose(a, np.dot(a, np.dot(B, a)))
    True
    >>> np.allclose(B, np.dot(B, np.dot(a, B)))
    True

    """
    a = _asarray_validated(a, check_finite=check_finite)
    s, u = decomp.eigh(a, lower=lower, check_finite=False)

    if rcond is not None:
        cond = rcond
    if cond in [None, -1]:
        t = u.dtype.char.lower()
        factor = {'f': 1E3, 'd': 1E6}
        cond = factor[t] * np.finfo(t).eps

    # For Hermitian matrices, singular values equal abs(eigenvalues)
    above_cutoff = (abs(s) > cond * np.max(abs(s)))
    psigma_diag = 1.0 / s[above_cutoff]
    u = u[:, above_cutoff]

    B = np.dot(u * psigma_diag, np.conjugate(u).T)

    if return_rank:
        return B, len(psigma_diag)
    else:
        return B
